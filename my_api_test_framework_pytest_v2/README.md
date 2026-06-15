# 🚀 Automated API Testing Framework — Dual Runner Edition

A Python-based API testing framework that supports **two complementary execution modes** sharing one set of utilities:

| Runner | When to use |
|---|---|
| **Pytest** | Local dev, CI, debugging — gives you fixtures, markers, parallelism, HTML reports |
| **Custom (`main_function.py`)** | Scheduled/batch runs — pulls test cases from S3, executes sequentially, uploads results back to S3 |

Both runners share `api_functions/` and `common_functions/`, so there's exactly **one source of truth** for HTTP, AWS, and config behavior.

---

## ✨ Features

- 🧪 **Pytest patterns** — `conftest.py` fixtures, `@pytest.mark.parametrize`, dynamic parametrization via `pytest_generate_tests`, custom markers (`smoke`, `regression`, `slow`, `aws`, `parametrized`, `contract`, `negative`)
- 🔄 **Data-driven** — same `tests/data/test_cases.json` consumed by both runners
- 📑 **JSON-schema contract validation** — responses validated against a published schema
- ☁️ **AWS S3 integration** — fetch test data, upload result artifacts (lazy-imported, so the framework runs without `boto3` installed)
- 🚦 **Parallel execution** — `pytest -n auto` via `pytest-xdist`
- 🔁 **Auto-retry flaky tests** — `pytest-rerunfailures` baked into requirements
- 📊 **HTML report** — `pytest --html=report.html`
- 🏗️ **CI-ready** — GitHub Actions matrix across Python 3.10 / 3.11 / 3.12
- 🌍 **Multi-env** — `TEST_ENV=qa|staging|prod` switches base URLs + auth
- 🎚️ **Strict markers** — undefined markers fail at collection time (no silent typos)

---

## 📁 Project Structure

```
my_api_test_framework_pytest/
├── README.md                            # You are here
├── pytest.ini                           # Markers, options, log config
├── requirements.txt                     # Pinned dependencies
├── conftest.py                          # Session-scoped fixtures (env, client, S3, data)
├── .gitignore
│
├── api_functions/                       # ⚙️ Shared utility — HTTP layer
│   ├── __init__.py
│   └── http_client.py                   # APIClient(requests.Session + retries + auth)
│
├── common_functions/                    # ⚙️ Shared utility — config / AWS / results
│   ├── __init__.py
│   ├── config_loader.py                 # Env-var + JSON file resolution
│   ├── aws_helper.py                    # S3 download / upload (lazy boto3 import)
│   └── result_writer.py                 # Aggregates results into JSON + summary.txt
│
├── tests/                               # 🧪 Pytest-discoverable tests
│   ├── __init__.py
│   ├── test_api_health.py               # Smoke tests with @pytest.mark.smoke
│   ├── test_api_users.py                # @pytest.mark.parametrize examples
│   ├── test_data_driven.py              # pytest_generate_tests + JSON-schema contract
│   └── data/
│       └── test_cases.json              # Shared input for BOTH runners
│
├── main_function.py                     # 🏃 Custom batch runner (S3-aware)
├── test_config.py                       # TestCaseSchema dataclass
│
└── .github/workflows/tests.yml          # CI: smoke on every PR, regression manual/nightly
```

---

## 🛠️ Prerequisites

- 🐍 **Python 3.10+**
- 🏠 Virtual environment (recommended)
- ☁️ AWS account (optional — only for the `aws` marker)

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/Karthick-71/my_api_test_framework_pytest.git
cd my_api_test_framework_pytest

# 2. Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Run smoke tests
pytest -m smoke

# 4. Run everything except slow tests, in parallel, with HTML report
pytest -m "not slow" -n auto --html=report.html --self-contained-html
```

That's it. The default config points at `httpbin.org` (a public sandbox) so the demo runs offline with no secrets.

---

## 🧪 Pytest Commands — Cheat Sheet

```bash
pytest                                  # All tests
pytest -m smoke                         # Smoke only
pytest -m regression                    # Regression only
pytest -m "regression and not slow"     # Composite marker filter
pytest -m "smoke or contract"           # OR composite
pytest tests/test_api_users.py          # Single file
pytest -k "http_404"                    # Tests whose name contains the keyword
pytest --collect-only -m smoke          # Preview what would run, without running
pytest -n auto                          # Parallel (one worker per CPU)
pytest --reruns 2 --reruns-delay 1      # Auto-retry flaky tests
pytest --html=report.html --self-contained-html   # HTML report
pytest -v --tb=short                    # Verbose + short traceback
pytest -s                               # Show print() output (don't capture stdout)
TEST_ENV=staging pytest -m smoke        # Override env
```

---

## 🏃 Custom Runner Commands

```bash
python main_function.py                                       # All cases, default env
python main_function.py --env staging                         # Different env
python main_function.py --tags smoke happy_path               # Filter by tag
python main_function.py --input /tmp/my_cases.json            # Custom input file
python main_function.py --output-dir /tmp/results --upload    # Upload results to S3
```

Both runners consume `tests/data/test_cases.json` by default — the schema is in `test_config.py:TestCaseSchema`.

---

## 🌍 Environment Configuration

The framework resolves config in this order (later wins):

1. **Defaults** in `common_functions/config_loader.py` (sandbox URLs that always work)
2. **JSON file** at `config/<env>.json` (gitignored — example shape in `config/qa.example.json`)
3. **Env vars** — `TEST_BASE_URL`, `TEST_AUTH_USER`, `TEST_AUTH_PASS`, `TEST_S3_BUCKET`, `AWS_REGION`

For local dev, drop a `.env` file (also gitignored — `python-dotenv` loads it).

---

## 📊 Reports

Pytest produces:
- **Terminal output** — colored, verbose, with per-marker summary
- **HTML report** — `pytest --html=report.html` → standalone file, shareable
- **JUnit XML** — `pytest --junitxml=results.xml` for Jenkins/CircleCI

Custom runner produces:
- **`test_results/results.json`** — every case with status, duration, payload, response detail
- **`test_results/summary.txt`** — human-readable totals
- **S3 upload** (with `--upload`) — `s3://<bucket>/results/run_<timestamp>.json`

---

## 🔧 Extending — Add a New Test

### Via Pytest (recommended)

```python
# tests/test_my_feature.py
import pytest

@pytest.mark.regression
@pytest.mark.parametrize("user_id, expected_status", [
    (1, 200),
    (999, 404),
])
def test_get_user(api_client, user_id, expected_status):
    resp = api_client.get(f"/users/{user_id}")
    assert resp.status_code == expected_status
```

### Via the JSON data file (works for both runners)

```json
{
  "test_name": "get_user_42",
  "method": "GET",
  "endpoint": "/users/42",
  "expected_status": 200,
  "tags": ["regression", "happy_path"]
}
```

Append to `tests/data/test_cases.json` — both `pytest` and `python main_function.py` will pick it up automatically.

---

## 🎯 Design Decisions

| Decision | Why |
|---|---|
| Two runners sharing one utility layer | Migration path from legacy custom runner to idiomatic Pytest without rewriting business logic |
| `conftest.py` at root level | Fixtures available to every test, including data-driven dynamic tests |
| `httpbin.org` as the default sandbox | Demo runs offline-friendly, no API keys required |
| `--strict-markers` enabled | Typo in a marker fails fast at collection — no silent test skips |
| Lazy `boto3` import | Framework still installable on minimal Python image without `boto3` |
| Session-scoped HTTP client | One auth handshake per session, not per test |
| JSON over xlsx for ships-in-repo data | Diff-friendly, parseable from any language, no Excel dependency |
| Auto-retry plugin baked in | Network flakiness is the most common false negative — retry once before failing |

---

## 🧭 Roadmap / TODO

- [ ] OpenAPI spec ingestion — auto-generate contract tests from `openapi.yml`
- [ ] Postman collection runner — Newman bridge
- [ ] Mutation testing for the validators themselves
- [ ] Locust load profile alongside the Pytest suite
- [ ] Allure reporter integration

---

## 📜 License

MIT

# Tests

This directory contains pytest-based tests for the WMS downloaders.

## Running Tests

### Install dependencies
```bash
pip install -e .[dev]
# or with uv:
uv sync --group dev
```

### Run all tests
```bash
pytest tests/
```

### Run with verbose output
```bash
pytest tests/ -v
```

### Generate HTML report
```bash
pytest tests/ --html=test-report.html --self-contained-html
```

### Run in parallel (faster)
```bash
pytest tests/ -n auto
```

## Test Structure

- `download_test.py`: Tests WMS downloads for all German federal states
  - **Critical states**: Bayern and Baden-Württemberg (must pass)
  - **Non-critical states**: Other states (failures are informational)

## CI/CD

Tests run automatically:
- On every pull request to `develop` or `main`
- Before publishing to PyPI (on version tags)

The CI fails only if Bayern or Baden-Württemberg downloads fail. Other state failures are marked as expected failures (`xfail`) and don't block the build.

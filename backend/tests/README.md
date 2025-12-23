# Sentiment Aggregator Test Suite

Comprehensive test coverage for the sentiment aggregation system.

## Test Structure

```
tests/
├── conftest.py                      # Shared fixtures and test utilities
├── test_sentiment_aggregator.py     # Core aggregator logic tests
├── test_sentiment_sources.py        # Individual source tests
├── fixtures/                        # Mock data and test fixtures
│   └── __init__.py
└── README.md                        # This file
```

## Running Tests

### Run All Tests
```bash
pytest
```

### Run with Coverage Report
```bash
pytest --cov=. --cov-report=html
```

### Run Specific Test Categories

**Unit tests only:**
```bash
pytest -m unit
```

**Integration tests only:**
```bash
pytest -m integration
```

**Skip slow tests:**
```bash
pytest -m "not slow"
```

**Skip external API tests:**
```bash
pytest -m "not external_api"
```

### Run Specific Test File
```bash
pytest tests/test_sentiment_aggregator.py
```

### Run Specific Test Class
```bash
pytest tests/test_sentiment_aggregator.py::TestSymbolNormalization
```

### Run Specific Test
```bash
pytest tests/test_sentiment_aggregator.py::TestSymbolNormalization::test_normalize_symbol_basic
```

## Test Markers

Tests are categorized with the following markers:

- **`@pytest.mark.unit`** - Fast unit tests for individual functions
- **`@pytest.mark.integration`** - Integration tests for multi-component workflows
- **`@pytest.mark.slow`** - Tests that take more than a few seconds
- **`@pytest.mark.external_api`** - Tests requiring external API calls (skip in CI)
- **`@pytest.mark.redis`** - Tests requiring Redis connection

## Coverage Goals

- **Target:** >80% code coverage
- **Current:** Run `pytest --cov` to see current coverage

## Test Data

### Mock Fixtures

All mock data is defined in `conftest.py`:

- **`mock_fear_greed_response`** - Fear & Greed Index API response
- **`mock_coingecko_btc_response`** - CoinGecko BTC data
- **`mock_rss_feed_response`** - RSS feed with 3 articles
- **`mock_reddit_response`** - Reddit posts with sentiment
- **`mock_vader_scores`** - VADER sentiment analysis results
- **`mock_sentiment_config`** - Complete configuration object
- **`mock_cache`** - In-memory cache for testing

### Using Fixtures

```python
def test_example(mock_fear_greed_response):
    # Use the fixture
    assert mock_fear_greed_response["data"][0]["value"] == "65"
```

## Writing New Tests

### Test Naming Convention

- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

### Example Test Structure

```python
import pytest
from unittest.mock import Mock, patch

class TestMyFeature:
    """Tests for my feature."""

    @pytest.mark.unit
    def test_basic_functionality(self):
        """Test basic case."""
        # Arrange
        input_data = "test"

        # Act
        result = my_function(input_data)

        # Assert
        assert result == expected_output

    @pytest.mark.integration
    @patch('module.external_dependency')
    def test_with_mocking(self, mock_dep):
        """Test with mocked dependency."""
        # Arrange
        mock_dep.return_value = "mocked value"

        # Act
        result = my_function()

        # Assert
        assert result is not None
        mock_dep.assert_called_once()
```

## Continuous Integration

### GitHub Actions (if configured)

Tests run automatically on:
- Pull requests
- Pushes to main branch
- Scheduled daily runs

### Pre-commit Hooks

Tests can be run via pre-commit:
```bash
pre-commit run pytest --all-files
```

## Troubleshooting

### Common Issues

**Import errors:**
```
ImportError: cannot import name 'function' from 'module'
```
- Check that the function exists in the module
- Verify the import path is correct
- Some tests are marked to skip if modules aren't available

**Async test failures:**
```
RuntimeError: no running event loop
```
- Ensure test is marked with `@pytest.mark.asyncio`
- Check that `pytest-asyncio` is installed

**Coverage below threshold:**
```
FAIL Required test coverage of 80% not reached
```
- Add more tests to increase coverage
- Or adjust threshold in `pytest.ini`

### Debug Mode

Run with verbose output and debug info:
```bash
pytest -vv --tb=long --log-cli-level=DEBUG
```

## Test Quality Guidelines

1. **Independence:** Tests should not depend on each other
2. **Repeatability:** Tests should produce same results every run
3. **Fast:** Unit tests should run in milliseconds
4. **Clear:** Test names should describe what they test
5. **Comprehensive:** Test happy path, edge cases, and error scenarios

## Next Steps

1. ✅ Set up test infrastructure
2. ✅ Create initial test suites
3. ⏳ Run tests and fix failures
4. ⏳ Increase coverage to 80%+
5. ⏳ Add integration tests for full pipeline
6. ⏳ Set up CI/CD pipeline

---

**Last Updated:** 2025-12-22
**Test Framework:** pytest 8.3.5
**Python Version:** 3.13+

.PHONY: test test-backend test-smoke

test: test-backend test-smoke

# Run backend unit tests with pytest
test-backend:
	@echo "[test] Running backend unit tests..."
	@cd backend && pytest

# Run smoke tests against running backend (assumes backend is listening on port 5001)
test-smoke:
	@echo "[test] Running smoke tests..."
	@bash smoke_test.sh http://localhost:5001

.PHONY: setup run lint clean clean-venv test_server

PYTHON := python3

# setup python environment
setup:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	@echo ""
	@echo "✓ Setup complete!"
	@echo ""
	@echo "To activate the virtual environment, run:"
	@echo "  source .venv/bin/activate"
	@echo ""
	@echo "Or use the setup script:"
	@echo "  source setup.sh"
	@echo ""

# run the server
run:
	@if [ -d .venv ]; then \
		.venv/bin/python src/server.py; \
	else \
		$(PYTHON) src/server.py; \
	fi

# lint and format the code with flake8 and black
lint:
	@echo "Running flake8..."
	@if [ -d .venv ]; then \
		.venv/bin/flake8 src/ --max-line-length=79; \
	else \
		flake8 src/ --max-line-length=79; \
	fi
	@echo "Formatting code with black..."
	@if [ -d .venv ]; then \
		.venv/bin/black src/ --line-length=79; \
	else \
		black src/ --line-length=79; \
	fi
	@echo "✓ Linting and formatting complete!"

# clean up cache files
clean:
	@echo "Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@find . -type f -name "*.py~" -delete
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleanup complete!"

# remove virtual environment
clean-venv:
	@echo "Removing virtual environment..."
	@rm -rf .venv
	@echo "✓ Virtual environment removed!"

# run curl commands in a loop to test the server and print the response
test_server:
	@echo "Testing server..."
	@for i in {1..10}; do \
		echo -n "Request $$i: "; \
		curl -x http://127.0.0.1:8888 http://example.com -s -o /dev/null -w "HTTP Status: %{http_code}\n"; \
	done


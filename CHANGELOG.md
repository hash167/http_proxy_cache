# Changelog

## [Unreleased]

### Added
- HTTP/HTTPS proxy server with multi-worker architecture
- SO_REUSEPORT for kernel-level load balancing (macOS & Linux compatible)
- Non-blocking I/O with event-driven architecture
- HTTPS tunneling via CONNECT method
- HTTP request/response parsing
- Configuration via environment variables
- Test suite with pytest (34 tests)
- Development tooling (flake8, black, Makefile targets)

### Fixed
- macOS socket compatibility (switched from FD passing to SO_REUSEPORT)
- HTTP request parsing for request line and headers
- Host:port parsing for custom ports
- Connection state machine validation
- Socket cleanup and error handling
- Renamed `http.py` → `http_parser.py` (stdlib conflict)

## [0.1.0] - 2025-11-16
- Initial project setup
- Multiprocessing with event-loop setup


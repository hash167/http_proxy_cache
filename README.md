# HTTP Proxy Cache Server

A high-performance HTTP proxy server with caching capabilities, built using Python's low-level socket programming with event driven architecture (rather than threads) and multiprocessing.

## Current Status

### ✅ Completed Features

#### Core Infrastructure
- **Multi-worker architecture** using `SO_REUSEPORT` for load balancing
- **Non-blocking I/O** using Python's `selectors` module
- **Configuration management** via environment variables or defaults

#### Connection Handling
- Accept incoming client connections
- Non-blocking socket operations
- Connection state machine (defined, not fully implemented)
- Basic socket data reading
- Simple HTTP response (200 OK)
- Clean connection cleanup and error handling


### 🚧 Remaining Work

- HTTP Request Parsing
- HTTP Response Handling
- Upstream Connection Management
- Caching Layer
- State Machine Implementation
- Error Handling & Edge Cases
- Testing & Reliability
- Documentation

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Main Process                    │
│  - Loads configuration                           │
│  - Spawns worker processes                       │
└───────────────┬─────────────────────────────────┘
                │
        ┌───────┴────────┬─────────────┬───────────┐
        │                │             │           │
┌───────▼──────┐ ┌──────▼──────┐ ┌───▼──────┐ ┌──▼──────┐
│   Worker 0   │ │  Worker 1   │ │Worker 2  │ │  ...    │
│              │ │             │ │          │ │         │
│ ┌──────────┐ │ │ ┌─────────┐ │ │┌────────┐│ │         │
│ │SO_REUSE  │ │ │ │SO_REUSE │ │ ││SO_REUSE││ │         │
│ │PORT sock │ │ │ │PORT sock│ │ ││PORT sock││ │         │
│ └────┬─────┘ │ │ └────┬────┘ │ │└───┬────┘│ │         │
│      │       │ │      │      │ │    │     │ │         │
│  ┌───▼────┐  │ │  ┌───▼───┐  │ │┌───▼───┐ │ │         │
│  │Selector│  │ │  │Selector│ │ ││Selector││ │         │
│  │ Event  │  │ │  │ Event │  │ ││ Event  ││ │         │
│  │ Loop   │  │ │  │ Loop  │  │ ││ Loop   ││ │         │
│  └────────┘  │ │  └───────┘  │ │└────────┘│ │         │
│              │ │             │ │          │ │         │
│ Connections  │ │Connections  │ │Connections│ │         │
│ Cache Access │ │Cache Access │ │Cache Access│ │         │
└──────────────┘ └─────────────┘ └───────────┘ └─────────┘
```

## Usage

### Setup

```bash
# Create virtual environment and install dependencies
make setup

# Activate the virtual environment
source .venv/bin/activate
```

### Running the Server

```bash
# Run with defaults (automatically uses .venv if available)
LISTEN_PORT=3128 NUM_WORKERS=4  make run
```

### Testing

`make test_server`
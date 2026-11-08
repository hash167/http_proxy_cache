# HTTP Proxy Cache Server

A small Python HTTP proxy. A parent process starts several **worker processes**. Each worker has its own listening socket and its own event loop, and can watch more than one socket at a time. Clients connect to the proxy’s IP address and port. They never address a worker by name.

The repository name says “cache,” and the configuration object has cache fields. Cache access on each worker is planned, as in the intended architecture below, and it does not run yet. The HTTP path that runs today is a first cut: it can accept connections, parse request headers, forward one plain HTTP request on a blocking upstream socket, and open a CONNECT tunnel. It is not a finished proxy, and it is not equivalent to nginx.

The server itself uses the Python standard library. [requirements.txt](requirements.txt) installs test and lint tools.

## Current status

### Running today

- The parent in [src/server.py](src/server.py) loads [ProxyConfig.from_env](src/datastructures.py) and starts one `multiprocessing.Process` per worker. It then waits on those processes. It does not listen itself, and it does not start a replacement if a worker exits.
- Each worker, `worker()` in [src/worker.py](src/worker.py), builds its own `AF_INET` / `SOCK_STREAM` listening socket, sets `SO_REUSEPORT` and `SO_REUSEADDR`, binds the shared address, and calls `listen`. The socket is non-blocking.
- The worker runs a `selectors.DefaultSelector` loop. On Linux, CPython’s default selector is typically epoll. The listen socket and accepted client sockets are registered for readability.
- `handle_accept` takes one pending connection off the listening socket with `accept()`, stores a `Connection`, and registers that connected socket.
- `handle_connection` reads the client with `recv(4096)` and appends to a buffer. If the blank line (`\r\n\r\n`) is not in the buffer yet, it returns to the selector and reads again later. [parse_http_request](src/http_parser.py) then reads the request line and headers.
- For a request other than `CONNECT`, the worker opens a **blocking** TCP connection with [connect_upstream](src/upstream.py), sends the buffered bytes once, and reads the upstream socket until it sees a header separator or the upstream closes. It sends whatever it collected to the client and closes the client. The upstream socket is not registered with the selector.
- For `CONNECT`, [handle_https_tunnel](src/tunnel.py) connects upstream, writes `HTTP/1.1 200 Connection Established`, and copies bytes both ways until one side finishes. That copy loop uses `select.select` on blocking sockets. It is not the worker’s selector loop.
- After one exchange the client connection is closed. There is no keep-alive.

### Present in the tree, not on this path

- `ConnectionState` includes `RECV_UPSTREAM`, `SEND_UPSTREAM`, and `SEND_CLIENT`. `handle_connection` has branches for them. A new `Connection` starts in `RECV_REQUEST`. The live path only changes that to `CLOSED`, and it never registers an upstream socket, so those branches do not run.
- `handle_upstream_connection` in [src/worker.py](src/worker.py) is not called. Its `finally` block closes the socket and the selector, so it is not a second loop ready to wire in.
- `send_request` and `receive_response` in [src/upstream.py](src/upstream.py) are not called by the server. `receive_response` performs a single `recv(4096)`.
- [build_http_response](src/http_parser.py) can build a `200`, `400`, or `404` message. The proxy loop does not call it. Tests do.
- `cache_size`, `cache_ttl`, `dns_cache_ttl`, `cache_key`, and `cache_response` are configuration and fields only.

### Not built

- A response cache or a DNS cache. That is the cache access drawn on each worker in the intended architecture. Nothing stores a response, honors a TTL, or reuses a lookup yet.
- Non-blocking upstream reads and writes on the worker selector.
- A complete HTTP message parser: no `Content-Length` framing, no chunked bodies, no hop-by-hop header handling, no request-line rewrite from absolute-form (`GET http://host/path`) to origin-form (`GET /path`).
- An enforced cap on simultaneous clients. `max_connections` is the `listen` backlog (default 1024), which limits how many not-yet-accepted connections the kernel will queue. The kernel may lower that number further. The accept loop does not count open clients.
- IPv6. Listening sockets are `AF_INET`, and `parse_host_port` splits on the first colon, so an IPv6 literal is not handled.
- Moving a connection between workers, or choosing a worker by round-robin or by which worker is least busy.

An earlier README listed HTTP parsing, upstream connections, tests, and the whole state machine as remaining work, and it described the server as answering with a simple `200 OK`. The code has moved on. Header parsing, a blocking forward, a CONNECT tunnel, and unit tests are in the tree. The running server forwards upstream bytes (or, for CONNECT, a fixed `200 Connection Established`). It does not build the simple `200 OK` that `build_http_response` knows how to build.

## Intended architecture

This is the architecture the project is building toward. The main process loads configuration and spawns worker processes. Each worker has its own `SO_REUSEPORT` listening socket, a selector event loop, the connections it has accepted, and cache access.

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

**Cache access** on each worker is planned. It is not implemented. `cache_size`, `cache_ttl`, `dns_cache_ttl`, `cache_key`, and `cache_response` are the fields set aside for it.

**Blocking upstream** is a separate limitation of the code that runs today. A plain HTTP forward still blocks in `connect_upstream` and `recv`, and a `CONNECT` tunnel still blocks in `handle_https_tunnel`, so that worker leaves its selector until the exchange finishes. The sections below describe that current behavior.

## Workers are processes

A **thread** runs inside a process and shares that process’s memory. A blocking call sleeps the thread that made it. Other threads in the same process can still run.

This program does not use a thread pool. [src/server.py](src/server.py) starts **processes**:

```python
worker_process = multiprocessing.Process(
    target=worker, args=(i, config)
)
worker_process.start()
```

Each worker is a separate operating-system process with its own Python interpreter, its own selector, its own listening socket, and its own `connections` dictionary. Worker `0` cannot see worker `1`’s sockets or buffers. The integer `i` is only the argument printed in that process’s startup line (`Worker 0 started and listening on 127.0.0.1:8888`). It is not a name a client can connect to.

Inside a worker there is one thread running the loop: that process’s main thread. When that thread blocks — in a blocking `recv` to an origin, or inside the CONNECT tunnel — that whole worker pauses. The other worker processes keep running. Nothing in this repository migrates the paused worker’s clients to them.

## Clients connect to an address, not to a worker

The default address is `127.0.0.1:8888`. Every worker binds that same IP and port. A client (curl, a browser, `requests`) connects to the address:

```text
client  ----TCP---->  127.0.0.1:8888
```

The client completes one TCP connection to that address. It does not choose “worker 2.” Which process calls `accept` is decided inside the kernel, from the listening sockets that share the port.

## What `SO_REUSEPORT` does here

Each worker creates a **new** listening socket after the process has started. The parent does not open a socket and pass the file descriptor down.

From `worker()`:

- `socket(AF_INET, SOCK_STREAM)`
- `setsockopt(SOL_SOCKET, SO_REUSEPORT, 1)`
- `setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)`
- `bind((listen_address, listen_port))`
- `listen(max_connections)`
- `setblocking(False)`

`SO_REUSEPORT` is what lets every worker bind the same address. `SO_REUSEADDR` is also set; it is a different option, the usual one for rebinding a port that still has a `TIME_WAIT` socket. Sharing the port among these workers is the `SO_REUSEPORT` setting. Linux also requires those processes to have the same effective UID, so one user cannot take another user’s port this way.

On current Linux kernels, listening sockets bound to the same address with `SO_REUSEPORT` are members of one **reuseport group**. For a new TCP connection the kernel picks one listening socket in that group and queues the connection there. The default pick is a **hash of the connection tuple** — the addresses and ports that identify the flow — scaled onto the sockets in the group.

That hash is a kernel policy, not a policy in this repository:

- The fields in the hash, and what happens to the mapping when a worker starts or exits, depend on the kernel version.
- A BPF program can replace the default. The socket options are `SO_ATTACH_REUSEPORT_CBPF` and `SO_ATTACH_REUSEPORT_EBPF`. This program does not attach one.
- Round-robin (take turns) and least-busy (pick the idle worker) are different policies. This code does not implement them, and the default Linux hash is neither one. A busy worker can still be chosen for the next new connection.
- `SO_REUSEPORT` dates from Linux 3.9. The reuseport-group structure came in with Linux 4.5, and TCP selection through that group in Linux 4.6. Older kernels still distribute new connections across the sockets. The program does not detect which variant it is running on.
- macOS also implements `SO_REUSEPORT`, which is why the same bind works there. The Linux group and tuple hash described above are Linux behavior. This program does not ask the host which rule it is using.

Once `accept()` returns, the new **connected** socket belongs to the process that accepted it. Later packets for that TCP connection are delivered to that socket. The other workers never see it, and this code never passes the file descriptor to them. If that worker is blocked in an upstream read or a tunnel, the connection stays there anyway.

## One worker, many sockets

Each worker creates one selector and registers every socket it wants to hear about:

```python
selector = selectors.DefaultSelector()
selector.register(listen_sock, selectors.EVENT_READ)  # no data object
```

Accepted clients are registered the same way, with the `Connection` object attached as the selector key’s data. The loop is:

```python
events = selector.select(timeout=1)
for key, mask in events:
    conn = key.data
    if conn is None:
        handle_accept(listen_sock, selector, connections)
    else:
        handle_connection(key, mask, selector, connections)
```

`selector.select(timeout=1)` waits up to one second. The wait happens in the operating system (epoll on Linux). The worker is suspended there. It is not spinning in Python. If a registered socket is already ready, the call returns with those events and does not sit out the rest of the second. If nothing is ready, it wakes when the timeout fires and loops again.

The selector can watch the listening socket and many client sockets in the same process. Each trip through the loop handles only the sockets that were reported ready. Registration is read interest only. The event mask is passed into `handle_connection` and ignored.

That is the shape of an event-driven loop. The current request path does not stay on that loop for the whole proxy:

- Plain HTTP calls `connect_upstream`, then blocking `send` and `recv`, before returning to `select`.
- `CONNECT` calls `handle_https_tunnel`, which blocks in its own `select.select` until the tunnel ends.

During either of those, this worker does not accept new connections and does not read its other clients. Those sockets stay registered, and they stay in this process.

## `accept` and `recv` are different calls

The listening socket and a connected client socket are two file descriptors.

**`accept()`** runs on the listening socket. It does not read HTTP. It takes one queued TCP connection and returns a new connected socket plus the peer address. In `handle_accept`:

```python
client_sock, addr = listen_sock.accept()
client_sock.setblocking(False)
```

**`recv()`** runs on a connected socket. `socket.socket.recv` is the standard-library method. It asks the operating system for bytes already stored in that socket’s **receive buffer** — the kernel memory that holds TCP data the peer has sent and this process has not read yet — and copies them into a Python `bytes` object. It does not parse HTTP.

```python
data = conn.socket.recv(4096)
```

`4096` is a maximum, not a message size. The call returns at most 4096 bytes, and it may return fewer. A short request often arrives in one read. A longer one arrives as several reads. Unread bytes stay in the kernel buffer until a later `recv`.

The worker appends each chunk to `Connection.recv_buffer` and looks for `\r\n\r\n`. Until that blank line is present it returns and waits for the selector to say the same client is readable again. That is how a partial read is supposed to work here.

Two consequences of the way the forward is written:

- The first time the buffer contains the header separator, the worker stops reading the client. A body that arrives in a later packet (a POST body, for example) is not added to the buffer first.
- The bytes it does have are sent upstream unchanged. A proxy request line in absolute-form (`GET http://host/path`) is not rewritten to origin-form (`GET /path`).

An empty result, `b""`, on a TCP socket means the peer has closed its sending side (EOF). The client path treats that as `ConnectionState.CLOSED`. A reset raises an exception instead of returning empty bytes; `handle_connection` then closes the client socket.

The upstream read in the same function is also `recv(4096)`, in a loop, into a separate `response` buffer. That loop stops at the first `\r\n\r\n` as well. The comment in the source says the body is assumed to be included. A response body that is still in the kernel buffer, or not received yet, is not fetched. The client then gets a single `send` of that buffer on a non-blocking socket, which may write only part of it. The tunnel path is the one that uses `sendall`.

## Blocking, non-blocking, and the would-block race

A new Python socket is **blocking**. If its receive buffer is empty and the peer has not closed, `recv` asks the kernel to suspend the calling thread until data arrives, the peer closes, an error occurs, or a timeout expires. The thread is asleep. It is not in a busy loop.

**Non-blocking** mode (`setblocking(False)`) means “do not suspend me.” If the call cannot finish immediately, it raises `BlockingIOError` (the kernel’s `EAGAIN` / `EWOULDBLOCK`).

What this program actually configures:

| Socket | Where it is created | Mode | Watched by |
| --- | --- | --- | --- |
| Listening socket | `worker()` | Non-blocking | The worker selector, read interest, no data object |
| Accepted client | `handle_accept` | Non-blocking | The worker selector, read interest, data is the `Connection` |
| Upstream for plain HTTP | `connect_upstream` | Blocking, the default | Nobody. Used with blocking `send` / `recv` inside `handle_connection` |
| Client and upstream during `CONNECT` | `handle_https_tunnel` switches them | Blocking, `settimeout(0.5)` | `select.select` inside the tunnel, not the worker selector |

So “the server is non-blocking” is only true of the listening socket and of client sockets while they sit on the selector. The forward and the tunnel deliberately block.

The selector is the efficient wait. `selector.select(timeout=1)` sleeps in the kernel while every registered socket is idle. When it returns, the loop calls `accept` or `recv` only for sockets it listed.

A readiness event is not a promise that the next call will succeed. The queued connection can be reset before `accept`, or the bytes can be gone before `recv`. The non-blocking call then raises `BlockingIOError`. A loop that wants to ignore that race catches it and returns to `select`. This code does not. `handle_accept` prints the error and re-raises it, and the worker’s outer handler then leaves the loop and shuts that worker down. `handle_connection` prints the error and closes that client. The parent keeps waiting on the remaining workers and does not start a new one.

## End to end, with four workers

Start four workers on port 3128:

```bash
LISTEN_PORT=3128 NUM_WORKERS=4 make run
```

`NUM_WORKERS=4` makes `main` start processes `0`, `1`, `2`, and `3`. Each binds `127.0.0.1:3128` as above and prints that same address. The parent is blocked in `join`.

Send a request through the proxy:

```bash
curl -x http://127.0.0.1:3128 http://example.com/
```

curl opens a TCP connection to `127.0.0.1:3128` and writes a proxy-style request. The request line and `Host` header look like this (curl also sends headers of its own, such as `User-Agent`):

```text
GET http://example.com/ HTTP/1.1
Host: example.com

```

What the processes do:

1. Linux picks one of the four listening sockets with its default tuple hash (see the caveats above). Suppose the hash lands on worker 2. Workers 0, 1, and 3 are not handed this connection. The next connection is a new tuple, and this program has no take-turns rule, so the next one can land on a different worker or on worker 2 again.
2. Worker 2 is inside `selector.select`. The listening socket becomes readable. Nothing was attached when it was registered, so `key.data` is `None`. The loop binds that to `conn` and calls `handle_accept`.
3. `accept()` returns a new connected socket, for example the peer `127.0.0.1:54321`. That file descriptor exists only in worker 2. Worker 2 sets it non-blocking, saves a `Connection` in `RECV_REQUEST`, and registers it.
4. When curl’s bytes arrive they sit in that socket’s receive buffer. The selector reports the client readable. `recv(4096)` copies out up to 4096 bytes. If the blank line is already in the buffer, parsing starts. If this read returned only `GET http://example.com/ HTTP/1.1\r\n`, the buffer has no `\r\n\r\n` yet, so the function returns. The connection stays registered. A later read appends the rest.
5. `parse_http_request` requires a request line of at least three fields and a `Host` header. Header lines are recognized when they contain the two bytes colon-space (`": "`). `Host: example.com` becomes hostname `example.com` and port `80` via `parse_host_port`. This branch uses the `Host` header for the origin. `CONNECT` is the branch that parses host and port from the request-target.
6. Worker 2 calls `connect_upstream(("example.com", 80))`. That is a new blocking socket and a blocking DNS lookup plus TCP handshake, started from this worker, to the origin. It is a different socket from the client, and it is not in the selector.
7. The worker `send`s `recv_buffer` to the origin, then blocking-`recv`s up to 4096 bytes at a time until the bytes collected from the origin contain `\r\n\r\n` or the origin closes. It `send`s that byte string to the client, closes the upstream socket, and marks the client `CLOSED`. Still inside this same `handle_connection` call, the `CLOSED` state unregisters and closes the client socket.
8. From step 6 through that close, worker 2 is not back in `selector.select`. Another client already accepted by worker 2 waits. A brand-new TCP connection can still be hashed onto worker 2: selection is independent of how busy the worker is. That new handshake waits in that listening socket’s backlog until this worker calls `accept` again.

A `CONNECT example.com:443` request, with a `Host` header, takes the other branch at step 5. `handle_https_tunnel` connects to `example.com:443`, sends `HTTP/1.1 200 Connection Established\r\n\r\n`, sets both sockets blocking with a 0.5 second timeout, and copies with `recv(8192)` and `sendall` until a side closes or errors. The worker’s selector is paused for the life of the tunnel. The tunnel does not decrypt TLS. It copies bytes.

Sketch of the same control flow, abbreviated from [src/server.py](src/server.py) and [src/worker.py](src/worker.py):

```python
# Parent — one process per worker, shared config, no listening socket here.
config = ProxyConfig.from_env()          # 127.0.0.1:3128, num_workers=4
for i in range(config.num_workers):      # i is 0, 1, 2, 3
    multiprocessing.Process(target=worker, args=(i, config)).start()
# parent then join()s every process; it does not listen

# Each worker process.
listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listen_sock.bind((config.listen_address, config.listen_port))
listen_sock.listen(config.max_connections)
listen_sock.setblocking(False)
selector = selectors.DefaultSelector()
selector.register(listen_sock, selectors.EVENT_READ)   # key.data is None

while True:
    for key, mask in selector.select(timeout=1):       # sleep while idle
        conn = key.data
        if conn is None:                                # listening socket
            client, addr = listen_sock.accept()        # new connected socket
            client.setblocking(False)
            selector.register(client, selectors.EVENT_READ, Connection(...))
        else:
            chunk = conn.socket.recv(4096)              # this client, at most 4096
            # append; on a blank line, parse, then block on upstream or tunnel
```

## How this compares with nginx

nginx’s usual process model is the same shape in two ways: several worker processes, and an event-driven loop in each worker so one process can have many sockets open. With nginx’s `reuseport` listen option, each worker has its own listening socket and Linux distributes new connections across them.

That is as far as the comparison goes. nginx is a mature server with a full HTTP state machine, upstream connection handling, and a real cache. This repository is an early proxy: the event loop accepts and reads headers, then blocks for the rest of a single request, and the cache names in the config are unused. Nothing here reproduces nginx’s load-balancing methods or its performance.

## Setup

```bash
make setup
source .venv/bin/activate
```

`make setup` creates `.venv` and installs [requirements.txt](requirements.txt). You can leave the virtualenv inactive: `make run` and `make test` use `.venv` when it exists.

### Run

```bash
make run
```

Defaults are `127.0.0.1`, port `8888`, and one worker per CPU (`multiprocessing.cpu_count()`). Override on the command line:

```bash
LISTEN_PORT=3128 NUM_WORKERS=4 make run
```

Point a client at the address you bound, not at a worker id:

```bash
curl -x http://127.0.0.1:3128 http://example.com/
```

The `test_server` Makefile target curls `127.0.0.1:8888`, which matches the default port. Use that target only when the proxy is on 8888.

Ctrl-C delivers `KeyboardInterrupt` to the processes in the foreground process group. Each worker catches it, closes its listening socket, closes sockets still in its `connections` dict, and closes its selector. The parent has no signal handler of its own; it is blocked in `join()`, so the interrupt surfaces there as well.

### Tests

```bash
make test
```

That runs pytest on [tests/](tests/). The unit tests cover request and response parsing, `ProxyConfig`, `ConnectionState`, and `parse_host_port`. They do not start the proxy.

The `proxy_server` fixture in [tests/test_integration.py](tests/test_integration.py) starts two workers on port `18888` for the integration class. One test checks that the port accepts a TCP connection. Two tests send a live request through the proxy to `httpbin.org` and **skip** on a proxy error, a timeout, or any other exception from the request. A run can look green without having completed those two requests. A fourth test in that file only checks that a closed port refuses a connection; it does not start the proxy.

### Lint

```bash
make lint
```

Runs flake8 on `src/`, then black, which formats `src/` in place.

## Configuration

`ProxyConfig.from_env` reads these variables. Unset variables use the defaults.

| Variable | Default | Used for |
| --- | --- | --- |
| `LISTEN_ADDRESS` | `127.0.0.1` | Bind address. IPv4 only (`AF_INET`). |
| `LISTEN_PORT` | `8888` | Bind port on every worker. |
| `NUM_WORKERS` | `multiprocessing.cpu_count()` | How many processes to start. Values below 1 raise `ValueError`. |
| `CACHE_SIZE` | `104857600` (100 MiB) | Stored on the config object. No cache reads it. Negative values raise. |
| `CACHE_TTL` | `300` | Stored on the config object. No cache reads it. Negative values raise. |
| `DNS_CACHE_TTL` | `300` | Stored on the config object. Lookups are ordinary blocking `connect` calls. |

`max_connections` is not an environment variable. It defaults to `1024` and is passed to `listen` as the backlog.

`ProxyConfig.__post_init__` is written to reject a port outside `1..65535`, but the condition requires the port to be both greater than 65535 and less than 1, so that check never fires. A bad port fails later, at `bind`, or when `int()` parses `LISTEN_PORT`.

## Source map

| File | Role |
| --- | --- |
| [src/server.py](src/server.py) | Load config, start worker processes, wait. |
| [src/worker.py](src/worker.py) | Listening socket, selector loop, `accept`, client `recv`, blocking forward. |
| [src/http_parser.py](src/http_parser.py) | Header parser. Response builder used by tests, not by the loop. |
| [src/upstream.py](src/upstream.py) | Blocking `connect`. The send/receive helpers are unused by the server. |
| [src/tunnel.py](src/tunnel.py) | `CONNECT` byte tunnel and `parse_host_port`. |
| [src/datastructures.py](src/datastructures.py) | `ProxyConfig`, `Connection`, `ConnectionState`. |

## Glossary

**Process.** An operating-system program with its own memory. The workers here are processes created with `multiprocessing.Process`.

**Thread.** A stream of execution inside a process. This server has no worker threads. Each worker’s loop is that process’s main thread, so a blocking call pauses that worker only.

**Listening socket.** A bound, `listen`ing socket. It has no peer. Its job is to queue new TCP handshakes. `accept()` creates a different socket for each one.

**Connected socket.** The socket `accept()` returns, tied to one peer, or the socket `connect()` returns toward an origin. `recv` and `send` run on connected sockets.

**`accept()`.** Listening-socket call that takes one queued connection and returns a new connected socket. It does not return HTTP bytes.

**`recv(n)`.** Connected-socket call that copies at most `n` bytes from that socket’s kernel receive buffer into Python. Fewer bytes are normal. `b""` on a TCP socket means EOF.

**Receive buffer.** Kernel memory for bytes the peer has sent on that TCP connection and the process has not read yet. `recv` drains it. It is not an HTTP message buffer; `Connection.recv_buffer` is the separate Python buffer this program appends to.

**Selector.** An object that sleeps until one of a set of sockets is ready, or until a timeout. This worker uses `selectors.DefaultSelector` and a one-second timeout. The CONNECT path uses `select.select` instead, on its two sockets.

**`BlockingIOError`.** What a non-blocking `accept` or `recv` raises when there is nothing to take. The worker loop does not catch it and retry.

**`SO_REUSEPORT`.** Socket option set on every listening socket so each worker can bind the same IP and port. Distribution of new connections is up to the host kernel.

**Reuseport group.** The set Linux uses, on current kernels, to hold those listening sockets. The default choice inside the group is a hash of the connection tuple, depending on kernel version, and it can be replaced with BPF. This program leaves the default in place.

**Connection tuple.** The addresses and ports that identify one flow. The kernel hashes that information to choose a listening socket. After `accept`, the established connection is no longer re-hashed onto another worker.

import socket
import selectors
from datastructures import Connection, ConnectionState, ProxyConfig
from http_parser import parse_http_request
from upstream import connect_upstream
from tunnel import handle_https_tunnel, parse_host_port


def handle_accept(
    listen_sock: socket.socket,
    selector: selectors.DefaultSelector,
    connections: dict[int, Connection],
) -> None:
    try:
        client_sock, addr = listen_sock.accept()
        client_sock.setblocking(False)
        connection = Connection(socket=client_sock, address=addr)
        connections[client_sock.fileno()] = connection
        selector.register(client_sock, selectors.EVENT_READ, connection)
    except Exception as e:
        print(f"Error accepting connection: {e}")
        raise e


def handle_connection(
    key: selectors.SelectorKey,
    mask: int,
    selector: selectors.DefaultSelector,
    connections: dict[int, Connection],
) -> None:
    conn = key.data
    try:
        if conn.state == ConnectionState.RECV_REQUEST:
            # Read data from the client
            data = conn.socket.recv(4096)
            if not data:
                # Client closed connection
                conn.state = ConnectionState.CLOSED
            else:
                conn.recv_buffer += data
                print(f"Received {len(data)} bytes from client")

                # Check if we have a complete HTTP request
                if b"\r\n\r\n" not in conn.recv_buffer:
                    # Keep receiving
                    return

                # Parse HTTP request
                http_request = parse_http_request(conn.recv_buffer)

                if not http_request or "Host" not in http_request:
                    print("Invalid HTTP request or missing Host header")
                    conn.state = ConnectionState.CLOSED
                    return

                method = http_request.get("method")
                url = http_request.get("url")
                print(f"Parsed request: {method} {url}")
                print(f"Host: {http_request.get('Host')}")

                # Handle CONNECT requests (HTTPS tunneling)
                if method == "CONNECT":
                    print("Handling CONNECT request for HTTPS tunneling")
                    # Delegate to tunnel module
                    handle_https_tunnel(conn.socket, url)
                    conn.state = ConnectionState.CLOSED
                    return

                # Parse host and port from Host header
                host_string = http_request.get("Host", "")
                if not host_string:
                    print("No Host header found")
                    conn.state = ConnectionState.CLOSED
                    return

                hostname, port = parse_host_port(host_string)
                print(f"Connecting to {hostname}:{port}")

                # Connect to upstream server (blocking for now)
                try:
                    conn.upstream_address = (hostname, port)
                    conn.upstream_socket = connect_upstream(
                        conn.upstream_address
                    )

                    # Send request to upstream (blocking)
                    sent = conn.upstream_socket.send(conn.recv_buffer)
                    print(f"Sent {sent} bytes to upstream")

                    # Receive response from upstream (blocking)
                    response = b""
                    while True:
                        data = conn.upstream_socket.recv(4096)
                        if not data:
                            break
                        response += data
                        # Simple check for complete HTTP response
                        if b"\r\n\r\n" in response:
                            # Check if we have the body too
                            # For now, assume we got it all
                            break

                    print(f"Received {len(response)} bytes from upstream")

                    # Send response back to client
                    conn.socket.send(response)
                    print(f"Sent {len(response)} bytes to client")

                    # Close upstream connection
                    conn.upstream_socket.close()

                except Exception as e:
                    print(f"Error proxying request: {e}")

                # Close client connection
                conn.state = ConnectionState.CLOSED

        elif conn.state == ConnectionState.RECV_UPSTREAM:
            print("Receiving upstream")
            data = conn.upstream_socket.recv(4096)
            if not data:
                conn.state = ConnectionState.CLOSED
            else:
                conn.recv_buffer += data
                print(f"Received {len(data)} bytes from upstream")
                conn.state = ConnectionState.SEND_CLIENT
        elif conn.state == ConnectionState.SEND_UPSTREAM:
            print("Sending upstream")
            data = conn.upstream_socket.send(conn.send_buffer)
            if not data:
                conn.state = ConnectionState.CLOSED
            else:
                conn.send_buffer = conn.send_buffer[data:]
                print(f"Sent {data} bytes to upstream")
                conn.state = ConnectionState.RECV_UPSTREAM
        elif conn.state == ConnectionState.SEND_CLIENT:
            print("Sending client")
            data = conn.socket.send(conn.send_buffer)
            if not data:
                conn.state = ConnectionState.CLOSED
            else:
                conn.send_buffer = conn.send_buffer[data:]
                print(f"Sent {data} bytes to client")
                conn.state = ConnectionState.RECV_UPSTREAM

        if conn.state == ConnectionState.CLOSED:
            print("Closing connection")
            try:
                fd = conn.socket.fileno()
                selector.unregister(conn.socket)
                conn.socket.close()
                if fd in connections:
                    del connections[fd]
            except Exception as e:
                print(f"Error closing connection: {e}")

    except Exception as e:
        print(f"Error handling connection: {e}")
        try:
            selector.unregister(conn.socket)
            conn.socket.close()
            if conn.socket.fileno() in connections:
                del connections[conn.socket.fileno()]
        except Exception:
            pass


def worker(id: int, config: ProxyConfig):
    # Each worker creates its own socket with SO_REUSEPORT
    # This allows multiple processes to bind to the same address/port
    # and the kernel will load balance connections across them
    listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen_sock.bind((config.listen_address, config.listen_port))
    listen_sock.listen(config.max_connections)
    listen_sock.setblocking(False)

    selector = selectors.DefaultSelector()
    selector.register(listen_sock, selectors.EVENT_READ)
    connections = {}

    print(
        f"Worker {id} started and listening on "
        f"{config.listen_address}:{config.listen_port}"
    )

    try:
        while True:
            events = selector.select(timeout=1)
            for key, mask in events:
                conn = key.data
                if conn is None:
                    # This is the listen socket
                    handle_accept(listen_sock, selector, connections)
                else:
                    # This is a client connection
                    handle_connection(key, mask, selector, connections)
    except KeyboardInterrupt:
        print(f"Worker {id} shutting down...")
    except Exception as e:
        print(f"Error in worker {id}: {e}")
    finally:
        listen_sock.close()
        for conn in connections.values():
            conn.socket.close()
        selector.close()


def handle_upstream_connection(
    key: selectors.SelectorKey,
    mask: int,
    selector: selectors.DefaultSelector,
    connections: dict[int, Connection],
) -> None:
    try:
        conn = key.data
        if conn.state == ConnectionState.RECV_UPSTREAM:
            data = conn.socket.recv(4096)
            if not data:
                conn.state = ConnectionState.CLOSED
            else:
                conn.recv_buffer += data
                print(f"Received {len(data)} bytes from upstream")
                conn.state = ConnectionState.SEND_CLIENT
        elif conn.state == ConnectionState.SEND_UPSTREAM:
            data = conn.socket.send(conn.send_buffer)
            if not data:
                conn.state = ConnectionState.CLOSED
            else:
                conn.send_buffer = conn.send_buffer[data:]
                print(f"Sent {data} bytes to upstream")
                conn.state = ConnectionState.RECV_UPSTREAM
        elif conn.state == ConnectionState.SEND_CLIENT:
            data = conn.socket.send(conn.send_buffer)
            if not data:
                conn.state = ConnectionState.CLOSED
            else:
                conn.send_buffer = conn.send_buffer[data:]
                print(f"Sent {data} bytes to client")
                conn.state = ConnectionState.RECV_UPSTREAM
    except Exception as e:
        print(f"Error handling upstream connection: {e}")
        try:
            selector.unregister(conn.socket)
            conn.socket.close()
            if conn.socket.fileno() in connections:
                del connections[conn.socket.fileno()]
        except Exception:
            pass
    finally:
        conn.socket.close()
        selector.close()

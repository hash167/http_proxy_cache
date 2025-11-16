import socket
import selectors
from datastructures import Connection, ConnectionState, ProxyConfig


def handle_accept(
        listen_sock: socket.socket,
        selector: selectors.DefaultSelector,
        connections: dict[int, Connection]) -> None:
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
        connections: dict[int, Connection]) -> None:
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
                # For now, just close the connection after receiving data
                # TODO: Parse HTTP request and handle properly
                conn.socket.send(b"HTTP/1.1 200 OK\r\n\r\n")
                conn.state = ConnectionState.CLOSED
        elif conn.state == ConnectionState.RECV_UPSTREAM:
            print("Receiving upstream")
        elif conn.state == ConnectionState.SEND_UPSTREAM:
            print("Sending upstream")
        elif conn.state == ConnectionState.SEND_CLIENT:
            print("Sending client")

        if conn.state == ConnectionState.CLOSED:
            print("Closing connection")
            selector.unregister(conn.socket)
            conn.socket.close()
            del connections[conn.socket.fileno()]

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

    print(f"Worker {id} started and listening on "
          f"{config.listen_address}:{config.listen_port}")

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

import socket
import select


def parse_host_port(host_string: str) -> tuple[str, int]:
    """
    Parse a host string that may include a port.
    Returns (hostname, port) tuple.
    """
    if ":" in host_string:
        parts = host_string.split(":")
        hostname = parts[0]
        try:
            port = int(parts[1])
        except (ValueError, IndexError):
            port = 80
        return (hostname, port)
    return (host_string, 80)


def handle_https_tunnel(client_socket: socket.socket, target_url: str):
    """
    Handle HTTPS tunneling for CONNECT requests.

    This establishes a bidirectional TCP tunnel between the client
    and the upstream server, allowing encrypted HTTPS traffic to pass
    through without inspection.

    Args:
        client_socket: The client's socket connection
        target_url: The target host:port from the CONNECT request
    """
    hostname, port = parse_host_port(target_url)
    print(f"Tunneling to {hostname}:{port}")

    upstream_socket = None

    try:
        # Connect to the upstream server
        upstream_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        upstream_socket.connect((hostname, port))

        # Send success response to client
        success_response = b"HTTP/1.1 200 Connection Established\r\n\r\n"
        client_socket.send(success_response)
        print("Sent 200 Connection Established to client")

        # Configure sockets for tunneling
        client_socket.setblocking(True)
        upstream_socket.setblocking(True)
        client_socket.settimeout(0.5)
        upstream_socket.settimeout(0.5)

        print("Starting bidirectional tunnel...")

        # Bidirectional tunneling loop
        try:
            while True:
                # Check which sockets are ready to read
                readable, _, exceptional = select.select(
                    [client_socket, upstream_socket],
                    [],
                    [client_socket, upstream_socket],
                    60.0,
                )

                if exceptional:
                    print("Exceptional condition on socket")
                    break

                if not readable:
                    # Timeout - continue to check for data
                    continue

                for sock in readable:
                    try:
                        data = sock.recv(8192)
                        if not data:
                            # Connection closed - normal end
                            print("Tunnel closed normally")
                            return  # Exit tunnel loop

                        # Forward data to the other socket
                        if sock is client_socket:
                            # Client -> Upstream
                            upstream_socket.sendall(data)
                            msg = (
                                f"Forwarded {len(data)} "
                                "bytes client->upstream"
                            )
                            print(msg)
                        else:
                            # Upstream -> Client
                            client_socket.sendall(data)
                            msg = (
                                f"Forwarded {len(data)} "
                                "bytes upstream->client"
                            )
                            print(msg)
                    except socket.timeout:
                        # Timeout is normal, continue
                        continue
                    except Exception as e:
                        print(f"Error forwarding: {e}")
                        return  # Exit on error
        except KeyboardInterrupt:
            print("Tunnel interrupted")
        except Exception as e:
            print(f"Tunnel error: {e}")

    except Exception as e:
        print(f"Error in CONNECT tunnel: {e}")
    finally:
        if upstream_socket:
            try:
                upstream_socket.close()
            except Exception:
                pass

import socket


def connect_upstream(upstream_address: tuple[str, int]) -> socket.socket:
    """
    Connect to an upstream address and return a socket.
    """
    upstream_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    upstream_socket.connect(upstream_address)
    return upstream_socket  # type: ignore


def send_request(upstream_socket: socket.socket, request: bytes) -> bytes:
    """
    Send a request to an upstream socket and return the response.
    """
    upstream_socket.send(request)
    return upstream_socket.recv(4096)


def receive_response(upstream_socket: socket.socket) -> bytes:
    """
    Receive a response from an upstream socket and return it as a bytes.
    """
    return upstream_socket.recv(4096)


def close_upstream(upstream_socket: socket.socket) -> None:
    """
    Close the connection to an upstream socket.
    """
    upstream_socket.close()

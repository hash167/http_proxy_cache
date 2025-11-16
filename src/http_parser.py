def parse_http_request(request: bytes) -> dict:
    """
    Parse an HTTP request and return a dictionary of the request headers.
    """
    lines = request.split(b"\r\n")
    if not lines:
        return {}

    # Parse request line (e.g., "GET http://example.com/ HTTP/1.1")
    request_line = lines[0].decode("utf-8")
    parts = request_line.split(" ")
    if len(parts) < 3:
        return {}

    method, url, version = parts[0], parts[1], parts[2]

    # Parse headers
    headers = {"method": method, "url": url, "version": version}

    for line in lines[1:]:
        if not line:
            # Empty line marks end of headers
            break
        if b": " in line:
            key, value = line.split(b": ", 1)
            headers[key.decode("utf-8")] = value.decode("utf-8")

    return headers


def build_http_response(status_code: int, headers: dict, body: bytes) -> bytes:
    """
    Build an HTTP response and return it as a bytes object.
    """
    reason = status_code_to_reason(status_code)
    response = f"HTTP/1.1 {status_code} {reason}\r\n"
    for key, value in headers.items():
        response += f"{key}: {value}\r\n"
    response += "\r\n"
    response_bytes = response.encode("utf-8")
    return response_bytes + body


def status_code_to_reason(status_code: int) -> str:
    """
    Return the reason phrase for a given status code.
    """
    return {
        200: "OK",
        400: "Bad Request",
        404: "Not Found",
    }[status_code]

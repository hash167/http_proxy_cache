import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from http_parser import parse_http_request, build_http_response, status_code_to_reason


class TestHTTPRequestParsing:
    """Test HTTP request parsing functionality"""

    def test_parse_simple_get_request(self):
        """Test parsing a simple GET request"""
        request = b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n"
        result = parse_http_request(request)

        assert result['method'] == 'GET'
        assert result['url'] == 'http://example.com/'
        assert result['version'] == 'HTTP/1.1'
        assert result['Host'] == 'example.com'

    def test_parse_request_with_port(self):
        """Test parsing request with port in Host header"""
        request = b"GET http://example.com:8080/ HTTP/1.1\r\nHost: example.com:8080\r\n\r\n"
        result = parse_http_request(request)

        assert result['method'] == 'GET'
        assert result['Host'] == 'example.com:8080'

    def test_parse_request_with_multiple_headers(self):
        """Test parsing request with multiple headers"""
        request = (
            b"GET http://example.com/ HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"User-Agent: TestClient/1.0\r\n"
            b"Accept: */*\r\n"
            b"\r\n"
        )
        result = parse_http_request(request)

        assert result['method'] == 'GET'
        assert result['Host'] == 'example.com'
        assert result['User-Agent'] == 'TestClient/1.0'
        assert result['Accept'] == '*/*'

    def test_parse_post_request(self):
        """Test parsing POST request"""
        request = (
            b"POST http://example.com/api HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Content-Type: application/json\r\n"
            b"\r\n"
        )
        result = parse_http_request(request)

        assert result['method'] == 'POST'
        assert result['url'] == 'http://example.com/api'
        assert result['Content-Type'] == 'application/json'

    def test_parse_connect_request(self):
        """Test parsing CONNECT request for HTTPS"""
        request = b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n"
        result = parse_http_request(request)

        assert result['method'] == 'CONNECT'
        assert result['url'] == 'example.com:443'
        assert result['Host'] == 'example.com:443'

    def test_parse_empty_request(self):
        """Test parsing empty request returns empty dict"""
        result = parse_http_request(b"")
        assert result == {}

    def test_parse_incomplete_request_line(self):
        """Test parsing incomplete request line"""
        request = b"GET\r\n"
        result = parse_http_request(request)
        assert result == {}


class TestHTTPResponseBuilding:
    """Test HTTP response building functionality"""

    def test_build_200_response(self):
        """Test building a 200 OK response"""
        response = build_http_response(200, {}, b"Hello World")

        assert b"HTTP/1.1 200 OK" in response
        assert b"Hello World" in response

    def test_build_404_response(self):
        """Test building a 404 Not Found response"""
        response = build_http_response(404, {}, b"Not Found")

        assert b"HTTP/1.1 404 Not Found" in response
        assert b"Not Found" in response

    def test_build_response_with_headers(self):
        """Test building response with custom headers"""
        headers = {
            "Content-Type": "text/html",
            "Content-Length": "5"
        }
        response = build_http_response(200, headers, b"Hello")

        assert b"Content-Type: text/html" in response
        assert b"Content-Length: 5" in response


class TestStatusCodeMapping:
    """Test status code to reason phrase mapping"""

    def test_status_200(self):
        assert status_code_to_reason(200) == "OK"

    def test_status_400(self):
        assert status_code_to_reason(400) == "Bad Request"

    def test_status_404(self):
        assert status_code_to_reason(404) == "Not Found"


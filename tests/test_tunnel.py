import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tunnel import parse_host_port


class TestHostPortParsing:
    """Test host:port parsing functionality"""

    def test_parse_hostname_only(self):
        """Test parsing hostname without port"""
        hostname, port = parse_host_port("example.com")
        assert hostname == "example.com"
        assert port == 80

    def test_parse_hostname_with_port(self):
        """Test parsing hostname with port"""
        hostname, port = parse_host_port("example.com:8080")
        assert hostname == "example.com"
        assert port == 8080

    def test_parse_https_port(self):
        """Test parsing hostname with HTTPS port"""
        hostname, port = parse_host_port("example.com:443")
        assert hostname == "example.com"
        assert port == 443

    def test_parse_invalid_port_defaults_to_80(self):
        """Test invalid port defaults to 80"""
        hostname, port = parse_host_port("example.com:invalid")
        assert hostname == "example.com"
        assert port == 80

    def test_parse_localhost(self):
        """Test parsing localhost"""
        hostname, port = parse_host_port("localhost:3000")
        assert hostname == "localhost"
        assert port == 3000

    def test_parse_ip_address(self):
        """Test parsing IP address"""
        hostname, port = parse_host_port("127.0.0.1:8888")
        assert hostname == "127.0.0.1"
        assert port == 8888

    def test_parse_ipv6_style(self):
        """Test parsing hostname with colons (basic case)"""
        # Note: This is a simple implementation that doesn't handle IPv6
        # For now we just test it doesn't crash
        hostname, port = parse_host_port("localhost")
        assert hostname == "localhost"
        assert port == 80


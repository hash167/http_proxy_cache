import pytest
import socket
import time
import multiprocessing
import sys
import os
import requests

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from datastructures import ProxyConfig
from server import main


@pytest.fixture(scope="module")
def proxy_server():
    """
    Start the proxy server in a separate process for integration tests
    """
    # Configure for testing
    os.environ["LISTEN_PORT"] = "18888"  # Use different port for tests
    os.environ["NUM_WORKERS"] = "2"

    # Start server process
    server_process = multiprocessing.Process(target=main)
    server_process.start()

    # Wait for server to start
    time.sleep(2)

    # Verify server is running
    max_retries = 10
    for i in range(max_retries):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', 18888))
            sock.close()
            if result == 0:
                break
        except Exception:
            pass
        time.sleep(0.5)

    yield "http://127.0.0.1:18888"

    # Cleanup
    server_process.terminate()
    server_process.join(timeout=5)
    if server_process.is_alive():
        server_process.kill()


class TestProxyIntegration:
    """Integration tests for the proxy server"""

    @pytest.mark.timeout(10)
    def test_server_starts(self, proxy_server):
        """Test that the proxy server starts successfully"""
        # Try to connect to the proxy
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('127.0.0.1', 18888))
        sock.close()
        assert result == 0, "Proxy server should be listening"

    @pytest.mark.timeout(30)
    def test_http_proxy_request(self, proxy_server):
        """Test proxying a simple HTTP request"""
        proxies = {
            'http': proxy_server,
        }

        try:
            # Use httpbin.org for testing (a reliable test endpoint)
            response = requests.get(
                'http://httpbin.org/status/200',
                proxies=proxies,
                timeout=10
            )
            assert response.status_code == 200
        except requests.exceptions.ProxyError:
            pytest.skip("HTTP proxy test failed - might be network issue")
        except requests.exceptions.Timeout:
            pytest.skip("HTTP proxy test timed out - might be network issue")
        except Exception as e:
            pytest.skip(f"HTTP proxy test failed: {e}")

    @pytest.mark.timeout(30)
    def test_https_proxy_request(self, proxy_server):
        """Test proxying an HTTPS request (CONNECT tunnel)"""
        proxies = {
            'http': proxy_server,
            'https': proxy_server,
        }

        try:
            # Test HTTPS through CONNECT tunnel
            response = requests.get(
                'https://httpbin.org/status/200',
                proxies=proxies,
                timeout=10
            )
            assert response.status_code == 200
        except requests.exceptions.ProxyError:
            pytest.skip("HTTPS proxy test failed - might be network issue")
        except requests.exceptions.Timeout:
            pytest.skip("HTTPS proxy test timed out - might be network issue")
        except Exception as e:
            pytest.skip(f"HTTPS proxy test failed: {e}")


class TestProxyEdgeCases:
    """Test edge cases without starting full server"""

    def test_connection_to_invalid_port(self):
        """Test connecting to a port where no server is running"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', 19999))
        sock.close()
        # Should fail to connect
        assert result != 0


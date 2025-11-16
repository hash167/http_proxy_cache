import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from datastructures import ProxyConfig, ConnectionState


class TestProxyConfig:
    """Test ProxyConfig dataclass"""

    def test_default_config(self):
        """Test default configuration values"""
        config = ProxyConfig()

        assert config.listen_address == "127.0.0.1"
        assert config.listen_port == 8888
        assert config.num_workers >= 1
        assert config.cache_size == 1024 * 1024 * 100
        assert config.cache_ttl == 300
        assert config.dns_cache_ttl == 300
        assert config.max_connections == 1024

    def test_custom_config(self):
        """Test custom configuration"""
        config = ProxyConfig(
            listen_address="0.0.0.0",
            listen_port=3128,
            num_workers=4,
            cache_size=200 * 1024 * 1024
        )

        assert config.listen_address == "0.0.0.0"
        assert config.listen_port == 3128
        assert config.num_workers == 4
        assert config.cache_size == 200 * 1024 * 1024

    def test_invalid_num_workers(self):
        """Test validation of num_workers"""
        with pytest.raises(ValueError, match="num_workers must be at least 1"):
            ProxyConfig(num_workers=0)

    def test_invalid_cache_size(self):
        """Test validation of cache_size"""
        with pytest.raises(ValueError, match="cache_size must be at least 0"):
            ProxyConfig(cache_size=-1)

    def test_invalid_cache_ttl(self):
        """Test validation of cache_ttl"""
        with pytest.raises(ValueError, match="cache_ttl must be at least 0"):
            ProxyConfig(cache_ttl=-1)

    def test_from_env_with_defaults(self):
        """Test loading from environment with defaults"""
        # Save original env
        original_env = os.environ.copy()

        try:
            # Clear relevant env vars
            for key in ["LISTEN_ADDRESS", "LISTEN_PORT", "NUM_WORKERS",
                        "CACHE_SIZE", "CACHE_TTL", "DNS_CACHE_TTL"]:
                os.environ.pop(key, None)

            config = ProxyConfig.from_env()
            assert config.listen_address == "127.0.0.1"
            assert config.listen_port == 8888
        finally:
            # Restore original env
            os.environ.clear()
            os.environ.update(original_env)

    def test_from_env_with_custom_values(self):
        """Test loading from environment with custom values"""
        # Save original env
        original_env = os.environ.copy()

        try:
            os.environ["LISTEN_PORT"] = "3128"
            os.environ["NUM_WORKERS"] = "2"

            config = ProxyConfig.from_env()
            assert config.listen_port == 3128
            assert config.num_workers == 2
        finally:
            # Restore original env
            os.environ.clear()
            os.environ.update(original_env)


class TestConnectionState:
    """Test ConnectionState enum"""

    def test_connection_states_exist(self):
        """Test all expected connection states exist"""
        assert hasattr(ConnectionState, 'RECV_REQUEST')
        assert hasattr(ConnectionState, 'RECV_UPSTREAM')
        assert hasattr(ConnectionState, 'SEND_UPSTREAM')
        assert hasattr(ConnectionState, 'SEND_CLIENT')
        assert hasattr(ConnectionState, 'CLOSED')

    def test_state_values(self):
        """Test connection state values"""
        assert ConnectionState.RECV_REQUEST.value == "RECV_REQUEST"
        assert ConnectionState.CLOSED.value == "CLOSED"

    def test_states_are_unique(self):
        """Test all states are unique"""
        states = [
            ConnectionState.RECV_REQUEST,
            ConnectionState.RECV_UPSTREAM,
            ConnectionState.SEND_UPSTREAM,
            ConnectionState.SEND_CLIENT,
            ConnectionState.CLOSED
        ]
        assert len(states) == len(set(states))


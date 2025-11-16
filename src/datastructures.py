import multiprocessing
from dataclasses import dataclass
import os
import socket
from enum import Enum
from typing import Optional


@dataclass
class ProxyConfig:
    listen_address: str = "127.0.0.1"
    listen_port: int = 8888
    num_workers: int = multiprocessing.cpu_count()
    cache_size: int = 1024 * 1024 * 100  # 100MB
    cache_ttl: int = 300  # 5 minutes
    dns_cache_ttl: int = 300  # 5 minutes
    max_connections: int = 1024

    def __post_init__(self):
        if self.num_workers < 1:
            raise ValueError("num_workers must be at least 1")
        if self.cache_size < 0:
            raise ValueError("cache_size must be at least 0")
        if self.cache_ttl < 0:
            raise ValueError("cache_ttl must be at least 0")
        if self.listen_port > 65535 and self.listen_port < 1:
            raise ValueError("listen_port must be between 1 and 65535")

    @classmethod
    def from_env(cls):
        return cls(
            listen_address=os.getenv("LISTEN_ADDRESS", "127.0.0.1"),
            listen_port=int(os.getenv("LISTEN_PORT", "8888")),
            num_workers=int(
                os.getenv("NUM_WORKERS", str(multiprocessing.cpu_count()))
            ),
            cache_size=int(os.getenv("CACHE_SIZE", str(1024 * 1024 * 100))),
            cache_ttl=int(os.getenv("CACHE_TTL", str(300))),
            dns_cache_ttl=int(os.getenv("DNS_CACHE_TTL", str(300))),
        )


# Connection state machine


class ConnectionState(Enum):
    RECV_REQUEST = "RECV_REQUEST"
    RECV_UPSTREAM = "RECV_UPSTREAM"
    SEND_UPSTREAM = "SEND_UPSTREAM"
    SEND_CLIENT = "SEND_CLIENT"
    CLOSED = "CLOSED"


@dataclass
class Connection:
    socket: socket.socket
    address: tuple[str, int]
    recv_buffer: bytes = b""
    send_buffer: bytes = b""
    state: ConnectionState = ConnectionState.RECV_REQUEST
    upstream_address: tuple[str, int] = None
    upstream_socket: Optional[socket.socket] = None
    target_port: int = 80
    target_host: str = ""
    cache_key: str = ""
    cache_response: Optional[bytes] = None

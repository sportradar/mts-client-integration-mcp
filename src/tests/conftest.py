from __future__ import annotations

import socket
from collections.abc import Generator

import pytest

from mts_client_integration.services.catalog import RejectionCatalog
from mts_client_integration.services.simulator.server import MockServerManager


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def catalog() -> RejectionCatalog:
    return RejectionCatalog.load()


@pytest.fixture
def mock_manager() -> Generator[MockServerManager]:
    manager = MockServerManager()
    yield manager
    if manager.is_running:
        manager.stop()


@pytest.fixture
def busy_port() -> Generator[int]:
    """A localhost port held open (listening) for the duration of the test."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        yield int(sock.getsockname()[1])

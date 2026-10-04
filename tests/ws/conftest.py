import asyncio
import uuid

import pytest

from app.ws.connection_manager import ConnectionManager


class FakeWebSocket:
    """Solo lo que usa el manager: send_json y close."""

    def __init__(self, fail: bool = False, hang: bool = False):
        self.sent: list[dict] = []
        self.closed_code: int | None = None
        self._fail = fail
        self._hang = hang

    async def send_json(self, data):
        if self._hang:
            await asyncio.Event().wait()  # cliente trabado: nunca termina
        if self._fail:
            raise RuntimeError("cliente desconectado")
        self.sent.append(data)

    async def close(self, code: int = 1000):
        self.closed_code = code


@pytest.fixture
def manager():
    return ConnectionManager(send_timeout=0.05)  # timeout corto: tests rápidos


@pytest.fixture
def channel():
    return uuid.uuid4()

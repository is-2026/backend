import asyncio
import uuid

from tests.ws.conftest import FakeWebSocket


async def test_broadcast_reaches_every_client_in_channel(manager, channel):
    a, b = FakeWebSocket(), FakeWebSocket()
    manager.connect(channel, a)
    manager.connect(channel, b)

    await manager.broadcast(channel, {"type": "matchState"})

    assert a.sent == b.sent == [{"type": "matchState"}]


async def test_broadcast_does_not_reach_other_channels(manager, channel):
    mine, other = FakeWebSocket(), FakeWebSocket()
    manager.connect(channel, mine)
    manager.connect(uuid.uuid4(), other)

    await manager.broadcast(channel, {"n": 1})

    assert other.sent == []


async def test_failing_client_is_dropped_and_others_keep_receiving(manager, channel):
    ok, broken = FakeWebSocket(), FakeWebSocket(fail=True)
    manager.connect(channel, ok)
    manager.connect(channel, broken)

    await manager.broadcast(channel, {"n": 1})
    await manager.broadcast(channel, {"n": 2})

    assert ok.sent == [{"n": 1}, {"n": 2}]
    assert not manager.is_connected(channel, broken)


async def test_hung_client_does_not_block_broadcast(manager, channel):
    ok, hung = FakeWebSocket(), FakeWebSocket(hang=True)
    manager.connect(channel, ok)
    manager.connect(channel, hung)

    # si el manager no corta por timeout, esto falla en 1 s en vez de colgarse
    await asyncio.wait_for(manager.broadcast(channel, {"n": 1}), 1)

    assert ok.sent == [{"n": 1}]
    assert not manager.is_connected(channel, hung)


async def test_disconnected_client_stops_receiving(manager, channel):
    ws = FakeWebSocket()
    manager.connect(channel, ws)

    manager.disconnect(channel, ws)
    manager.disconnect(channel, ws)  # dos veces no falla
    await manager.broadcast(channel, {"n": 1})

    assert ws.sent == []
    assert not manager.is_connected(channel, ws)


async def test_close_all_closes_every_client_with_code(manager, channel):
    a, b = FakeWebSocket(), FakeWebSocket()
    manager.connect(channel, a)
    manager.connect(channel, b)

    await manager.close_all(channel, code=4404)
    await manager.broadcast(channel, {"n": 1})

    assert a.closed_code == b.closed_code == 4404
    assert a.sent == b.sent == []

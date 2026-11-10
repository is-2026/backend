import asyncio
import uuid
from functools import partial

import pytest

from app.behaviors.defaults import DEFAULT_BEHAVIORS
from app.engine.state import Side
from app.ws.match import behavior_test, runner
from app.ws.match.behavior_test import (
    behavior_tests,
    build_test_info,
    build_test_state,
    start_behavior_test,
)
from app.ws.match.runner import live_matches, match_connections, stop_match
from tests.ws.conftest import FakeWebSocket

CODE = "def decide_action(): pass"


def _default_code(name: str) -> str:
    return next(b.code for b in DEFAULT_BEHAVIORS if b.name == name)


def _sides(state):
    home = next(p for p in state.players if p.side == Side.HOME)
    away = next(p for p in state.players if p.side == Side.AWAY)
    return home, away


@pytest.fixture
def waiting_start(monkeypatch):
    """La prueba queda esperando 60 s antes del primer tick: sirve para mirar el
    registro y el corte sin jugar. Se parchea el start_match que importó
    behavior_test (tiene su propia referencia), no el del runner."""
    monkeypatch.setattr(
        behavior_test, "start_match", partial(runner.start_match, start_delay=60)
    )


@pytest.fixture
def instant_start(monkeypatch):
    """La prueba juega los 600 ticks en un instante."""
    monkeypatch.setattr(
        behavior_test,
        "start_match",
        partial(runner.start_match, tick_interval=0, start_delay=0),
    )


@pytest.fixture(autouse=True)
async def cleanup():
    """Corta lo que haya quedado corriendo: cada prueba tiene 2 procesos hijos."""
    yield
    for live in list(behavior_tests.values()):
        await stop_match(live)
    behavior_tests.clear()


def test_build_test_state_sucess():
    state, _ = build_test_state(CODE)
    
    assert state.total_ticks == 600
    assert len(state.players) == 2
    assert {p.side for p in state.players} == {Side.HOME, Side.AWAY}

def test_build_test_state_codes_success():
    state, codes = build_test_state(CODE)
    home, away = _sides(state)

    assert codes == {home.id: CODE, away.id: _default_code("Defensor")}


def test_build_test_info_success():
    state, codes = build_test_state(CODE)  #cargo los jugadores
    home, away = _sides(state)

    info = build_test_info(state) #armo el partido

    assert [p.player_id for p in info.home_lineup] == [home.id]
    assert [p.player_id for p in info.away_lineup] == [away.id]
    assert {info.home_lineup[0].player_id, info.away_lineup[0].player_id} == set(codes)
    assert info.home_club.id == state.home_team_id
    assert info.away_club.id == state.away_team_id


def test_build_test_info_players_not_behavior_id(): 
    state, _ = build_test_state(CODE)

    info = build_test_info(state)

    assert info.home_lineup[0].behavior_id is None #chequeo que los jugadores no tengan id de comportamiento
    assert info.away_lineup[0].behavior_id is None # pues estan en memoria, no deberian tener.



async def test_start_registers_test(waiting_start): #queda esperando 60s antes del primer tick
    club_id = uuid.uuid4()

    match_id = await start_behavior_test(club_id, CODE)

    assert match_id in live_matches  #chequeo que el partido de prueba se cree en memoria
    assert behavior_tests[club_id].match_id == match_id


async def test_test_plays_600_ticks_without_pauses(instant_start): #se ejecutan los 600 ticks al instante
    club_id = uuid.uuid4()
    match_id = await start_behavior_test(club_id, CODE)
    ws = FakeWebSocket()
    match_connections.connect(match_id, ws)

    await behavior_tests[club_id].task

    types = [m["type"] for m in ws.sent] #armo la lista con cada msj que recibe el ws
    assert types.count("matchState") == 600
    assert not {"coolingBreakStart", "halftimeStart", "matchResumed"} & set(types) #chequeo que no haya pausas
    assert types[-1] == "matchFinished" #chequeo que se envia matchFinished al terminar el partido


async def test_second_test_cuts_first(waiting_start):
    club_id = uuid.uuid4()
    first_id = await start_behavior_test(club_id, CODE)
    first = behavior_tests[club_id]

    second_id = await start_behavior_test(club_id, CODE)

    assert first_id not in live_matches ## Chequeo que la primer prueba no este en memoria
    assert first.task.cancelled() ## Que la primer prueba haya sido cancelada
    assert second_id in live_matches ## que la segunda si este en memoria 
    assert behavior_tests[club_id].match_id == second_id ## que el id sea el correcto


async def test_other_club_does_not_cut(waiting_start): 
    match_a = await start_behavior_test(uuid.uuid4(), CODE)

    match_b = await start_behavior_test(uuid.uuid4(), CODE)

    assert match_a in live_matches ##pruebo que cada club tenga su prueba independiente
    assert match_b in live_matches


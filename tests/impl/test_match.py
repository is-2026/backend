import uuid
from datetime import datetime, timezone

import pytest

from app.db.behavior import BehaviorDB
from app.db.club import ClubDB
from app.db.user import UserDB
from app.engine.constants import TRIANGLE_HOME
from app.engine.executor import BehaviorExecutor
from app.engine.state import MatchState, Side
from app.security.tokens import create_access_token
from app.ws.match.info import ClubSummary, MatchInfo
from app.ws.match.runner import LiveMatch, live_matches
from tests.engine.conftest import make_player
from tests.ws.match.conftest import lineup_player

ON_FIELD = str(uuid.uuid4())
ON_BENCH = str(uuid.uuid4())


@pytest.fixture
async def club(session):
    """Usuario, club y un comportamiento de jugador reales en la base de test."""
    user = UserDB(email="hola@prueba.com", hashed_password="hash")
    session.add(user)
    await session.flush()
    club = ClubDB(club_name="Instituto", avatar_url="https://x/c.png", user_id=user.id)
    session.add(club)
    await session.flush()
    behavior = BehaviorDB(
        name="Atacante", code="def decide_action(): pass", club_id=club.id
    )
    session.add(behavior)
    await session.commit()
    return club, behavior


@pytest.fixture
def live(club):
    """Partido en juego del club (local): un titular en cancha y un suplente."""
    home_id, away_id = str(club[0].id), str(uuid.uuid4())
    state = MatchState(
        home_team_id=home_id,
        home_formation=TRIANGLE_HOME,
        away_team_id=away_id,
        away_formation=TRIANGLE_HOME,
        players=[make_player(ON_FIELD, Side.HOME)],
        total_ticks=3000,
    )
    info = MatchInfo(
        home_club=ClubSummary(id=home_id, name="Local", avatar_url="https://x/l.png"),
        away_club=ClubSummary(id=away_id, name="Visita", avatar_url="https://x/v.png"),
        home_lineup=[
            lineup_player(ON_FIELD, 1, True),
            lineup_player(ON_BENCH, 2, False),
        ],
        away_lineup=[],
    )
    live = LiveMatch(
        match_id=uuid.uuid4(),
        state=state,
        executor=BehaviorExecutor(state, {}),
        info=info,
        match_start=datetime.now(timezone.utc),
    )
    live_matches[live.match_id] = live
    yield live
    live_matches.pop(live.match_id, None)


def auth_header(club) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(club[0].user_id)}"}


def url(match_id) -> str:
    return f"/matches/{match_id}/substitutions"


def body(club, player_in=ON_BENCH) -> dict:
    return {
        "player_out_id": ON_FIELD,
        "player_in_id": player_in,
        "substitution_behavior_id": str(club[1].id),
    }


async def test_post_schedules_the_substitution(client, club, live):
    r = await client.post(
        url(live.match_id), json=body(club), headers=auth_header(club)
    )

    assert r.status_code == 201
    assert r.json()["status"] == "pending"
    assert r.json()["window"] == "cooling_break_1"
    assert str(club[0].id) in live.pending_substitutions


async def test_post_400_if_the_player_in_is_not_on_the_bench(client, club, live):
    r = await client.post(
        url(live.match_id),
        json=body(club, player_in=ON_FIELD),
        headers=auth_header(club),
    )

    assert r.status_code == 400
    assert live.pending_substitutions == {}


async def test_post_403_if_the_club_does_not_play_the_match(client, club, live):
    live.info.home_club.id = str(uuid.uuid4())

    r = await client.post(
        url(live.match_id), json=body(club), headers=auth_header(club)
    )

    assert r.status_code == 403


async def test_post_404_if_the_match_is_not_being_played(client, club):
    r = await client.post(url(uuid.uuid4()), json=body(club), headers=auth_header(club))

    assert r.status_code == 404


async def test_post_409_if_there_is_already_one_pending(client, club, live):
    await client.post(url(live.match_id), json=body(club), headers=auth_header(club))

    r = await client.post(
        url(live.match_id), json=body(club), headers=auth_header(club)
    )

    assert r.status_code == 409


async def test_delete_cancels_the_pending_substitution(client, club, live):
    await client.post(url(live.match_id), json=body(club), headers=auth_header(club))

    r = await client.delete(url(live.match_id), headers=auth_header(club))

    assert r.status_code == 200
    assert live.pending_substitutions == {}


async def test_delete_404_if_there_is_no_pending_one(client, club, live):
    r = await client.delete(url(live.match_id), headers=auth_header(club))

    assert r.status_code == 404

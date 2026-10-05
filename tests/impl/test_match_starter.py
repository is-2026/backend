import functools
import uuid

import pytest

from app.behaviors.defaults import DEFAULT_BEHAVIORS
from app.db.behavior import BehaviorDB
from app.db.club import ClubDB
from app.db.friendly import FriendlyDB, FriendlyPlayerDB
from app.db.match import MatchDB, MatchStatus
from app.db.player import PlayerDB
from app.db.user import UserDB
from app.ws.match import starter as starter_module
from app.ws.match.runner import live_matches, start_match
from app.ws.match.starter import MatchStarter


async def make_club_with_squad(session, name):
    user = UserDB(id=uuid.uuid4(), email=f"{name}@x.com", hashed_password="h")
    session.add(user)
    await session.flush()
    club = ClubDB(id=uuid.uuid4(), club_name=name, avatar_url="a", user_id=user.id)
    session.add(club)
    await session.flush()
    behavior = BehaviorDB(id=uuid.uuid4(), name="b", code=DEFAULT_BEHAVIORS[0].code, club_id=club.id)
    players = [
        PlayerDB(id=uuid.uuid4(), name=f"J{i}", number=i, power=60, agility=60,
                 control=60, speed=60, strength=60, club_id=club.id)
        for i in range(1, 7)
    ]
    session.add_all([behavior, *players])
    await session.flush()
    return club.id, behavior.id, players


@pytest.fixture
async def match_id(session):
    friendly_id, match_id = uuid.uuid4(), uuid.uuid4()
    home, home_b, home_players = await make_club_with_squad(session, "local")
    away, away_b, away_players = await make_club_with_squad(session, "visita")
    session.add(MatchDB(id=match_id, home_club_id=home, away_club_id=away))
    session.add(FriendlyDB(id=friendly_id, creator_club_id=home, rival_club_id=away,
                           status="accepted", match_id=match_id))
    await session.flush()
    for club, b, players in ((home, home_b, home_players), (away, away_b, away_players)):
        session.add_all(
            FriendlyPlayerDB(id=uuid.uuid4(), friendly_id=friendly_id, club_id=club,
                             player_id=p.id, is_starter=i < 3, behavior_id=b if i < 3 else None)
            for i, p in enumerate(players)
        )
    await session.commit()
    yield match_id
    live_matches.pop(match_id, None)


async def get_match(session_factory, match_id):
    async with session_factory() as s:
        return await s.get(MatchDB, match_id)


async def test_start_registers_match_and_sets_in_progress(session_factory, match_id, monkeypatch):
    monkeypatch.setattr(
        starter_module, "start_match",
        functools.partial(start_match, start_delay=60),  # que no arranque durante el test
    )
    starter = MatchStarter(session_factory)

    await starter.start(match_id)

    live = live_matches[match_id]
    assert len(live.state.players) == 6
    assert (await get_match(session_factory, match_id)).status == MatchStatus.in_progress
    live.task.cancel()


async def test_saves_result_when_finished(session_factory, match_id, monkeypatch):
    # el runner de verdad, pero sin esperar entre ticks: los 3000 ticks tardan menos de un segundo
    monkeypatch.setattr(
        starter_module, "start_match",
        functools.partial(start_match, tick_interval=0, start_delay=0),
    )
    starter = MatchStarter(session_factory)

    await starter.start(match_id)
    live = live_matches[match_id]
    (save_task,) = starter._tasks
    await save_task

    match = await get_match(session_factory, match_id)
    assert match.status == MatchStatus.finished
    assert (match.home_score, match.away_score) == (live.state.home_score, live.state.away_score)
    assert match_id not in live_matches


async def test_unknown_match_raises(session_factory):
    with pytest.raises(LookupError):
        await MatchStarter(session_factory).start(uuid.uuid4())

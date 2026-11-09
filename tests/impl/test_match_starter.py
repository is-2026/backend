import asyncio
import functools
import uuid
from types import SimpleNamespace

import pytest

from app.behaviors.defaults import DEFAULT_BEHAVIORS
from app.db.behavior import BehaviorDB
from app.db.club import ClubDB
from app.db.friendly import FriendlyDB, FriendlyPlayerDB
from app.db.league import LeagueDB, LeagueEnrollmentDB, LeagueEnrollmentPlayerDB
from app.db.match import MatchDB, MatchStatus
from app.db.player import PlayerDB
from app.db.standings import LeagueStandingsDB
from app.db.user import UserDB
from app.engine.constants import TICKS_PER_MINUTE
from app.engine.state import Side
from app.ws.match import starter as starter_module
from app.ws.match.runner import live_matches, start_match
from app.ws.match.starter import MatchStarter


async def make_club_with_squad(session, name):
    user = UserDB(id=uuid.uuid4(), email=f"{name}@x.com", hashed_password="h")
    session.add(user)
    await session.flush()
    club = ClubDB(
        id=uuid.uuid4(),
        club_name=name,
        avatar_url=f"https://x/{name}.png",
        user_id=user.id,
    )
    session.add(club)
    await session.flush()
    behavior = BehaviorDB(
        id=uuid.uuid4(),
        name="Atacante",
        code=DEFAULT_BEHAVIORS[0].code,
        club_id=club.id,
    )
    players = [
        PlayerDB(
            id=uuid.uuid4(),
            name=f"J{i}",
            number=i,
            power=60,
            agility=60,
            control=60,
            speed=60,
            strength=60,
            club_id=club.id,
        )
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
    await session.flush()  # el partido antes que el amistoso (FK friendlies.match_id)
    session.add(
        FriendlyDB(
            id=friendly_id,
            creator_club_id=home,
            rival_club_id=away,
            status="accepted",
            match_id=match_id,
        )
    )
    await session.flush()
    for club, b, players in (
        (home, home_b, home_players),
        (away, away_b, away_players),
    ):
        session.add_all(
            FriendlyPlayerDB(
                id=uuid.uuid4(),
                friendly_id=friendly_id,
                club_id=club,
                player_id=p.id,
                is_starter=i < 3,
                behavior_id=b if i < 3 else None,
            )
            for i, p in enumerate(players)
        )
    await session.commit()
    yield match_id
    live_matches.pop(match_id, None)


async def get_match(session_factory, match_id):
    async with session_factory() as s:
        return await s.get(MatchDB, match_id)


async def test_start_registers_match_with_info_and_sets_in_progress(
    session_factory, match_id, monkeypatch
):
    monkeypatch.setattr(
        starter_module,
        "start_match",
        functools.partial(
            start_match, start_delay=60
        ),  # que no arranque durante el test
    )
    starter = MatchStarter(session_factory)

    await starter.start(match_id)

    live = live_matches[match_id]
    assert len(live.state.players) == 6
    assert (live.info.home_club.name, live.info.away_club.name) == ("local", "visita")
    assert len(live.info.home_lineup) == len(live.info.away_lineup) == 6
    assert (
        await get_match(session_factory, match_id)
    ).status == MatchStatus.in_progress
    live.task.cancel()


async def test_saves_result_when_finished(session_factory, match_id, monkeypatch):
    # el runner de verdad, pero sin esperar entre ticks: los 3000 ticks tardan menos de un segundo
    monkeypatch.setattr(
        starter_module,
        "start_match",
        functools.partial(
            start_match,
            tick_interval=0,
            start_delay=0,
            cooling_break_duration=0,
            halftime_duration=0,
        ),
    )
    starter = MatchStarter(session_factory)

    await starter.start(match_id)
    live = live_matches[match_id]
    (save_task,) = starter._tasks
    await save_task

    match = await get_match(session_factory, match_id)
    assert match.status == MatchStatus.finished
    assert (match.home_score, match.away_score) == (
        live.state.home_score,
        live.state.away_score,
    )
    assert match_id not in live_matches


async def test_unknown_match_raises(session_factory):
    with pytest.raises(LookupError):
        await MatchStarter(session_factory).start(uuid.uuid4())


@pytest.fixture
async def league_match(session):
    league_id, match_id = uuid.uuid4(), uuid.uuid4()
    home, home_b, home_players = await make_club_with_squad(session, "local_liga")
    away, away_b, away_players = await make_club_with_squad(session, "visita_liga")
    session.add(
        LeagueDB(
            id=league_id,
            name="Liga",
            max_clubs=4,
            match_duration_minutes=2,
            status="started",
            creator_club_id=home,
        )
    )
    await session.flush()
    for rank, (club, b, players) in enumerate(
        ((home, home_b, home_players), (away, away_b, away_players)), start=1
    ):
        enrollment_id = uuid.uuid4()
        session.add(
            LeagueEnrollmentDB(id=enrollment_id, league_id=league_id, club_id=club)
        )
        session.add(LeagueStandingsDB(league_id=league_id, club_id=club, rank=rank))
        await session.flush()
        session.add_all(
            LeagueEnrollmentPlayerDB(
                id=uuid.uuid4(),
                enrollment_id=enrollment_id,
                player_id=p.id,
                is_starter=i < 3,
                behavior_id=b if i < 3 else None,
            )
            for i, p in enumerate(players)
        )
    session.add(
        MatchDB(
            id=match_id,
            home_club_id=home,
            away_club_id=away,
            league_id=league_id,
            round_number=1,
        )
    )
    await session.commit()
    yield league_id, match_id, home, away
    live_matches.pop(match_id, None)


async def test_league_match_uses_league_duration_and_updates_standings(
    session_factory, league_match, monkeypatch
):
    league_id, match_id, home, away = league_match
    monkeypatch.setattr(
        starter_module,
        "start_match",
        functools.partial(
            start_match,
            tick_interval=0,
            start_delay=0,
            cooling_break_duration=0,
            halftime_duration=0,
        ),
    )
    starter = MatchStarter(session_factory)

    save_task = await starter.start(match_id)
    live = live_matches[match_id]
    assert live.state.total_ticks == 2 * TICKS_PER_MINUTE
    await save_task

    async with session_factory() as s:
        match = await s.get(MatchDB, match_id)
        home_standing = await s.get(LeagueStandingsDB, (league_id, home))
        away_standing = await s.get(LeagueStandingsDB, (league_id, away))

    assert match.status == MatchStatus.finished
    assert (match.home_score, match.away_score) == (
        live.state.home_score,
        live.state.away_score,
    )
    assert home_standing.matches_played == 1
    assert away_standing.matches_played == 1
    assert (home_standing.goals_for, home_standing.goals_against) == (
        live.state.home_score,
        live.state.away_score,
    )
    assert (away_standing.goals_for, away_standing.goals_against) == (
        live.state.away_score,
        live.state.home_score,
    )


async def test_league_match_without_draws_passes_it_to_runner(
    session_factory, league_match, monkeypatch
):
    league_id, match_id, _, _ = league_match
    async with session_factory() as s:
        league = await s.get(LeagueDB, league_id)
        league.allows_draws = False
        await s.commit()
    monkeypatch.setattr(
        starter_module, "start_match", functools.partial(start_match, start_delay=60)
    )

    save_task = await MatchStarter(session_factory).start(match_id)
    live = live_matches[match_id]

    assert live.allows_draws is False
    live.task.cancel()
    await asyncio.gather(live.task, save_task, return_exceptions=True)


async def test_saves_penalties_when_there_was_a_shootout(session_factory, match_id):
    live = SimpleNamespace(
        match_id=match_id,
        task=asyncio.create_task(asyncio.sleep(0)),  # el runner ya terminó
        state=SimpleNamespace(home_score=1, away_score=1),
        shootout=SimpleNamespace(home_penalties=4, away_penalties=3),
    )

    await MatchStarter(session_factory)._save_result(live)

    match = await get_match(session_factory, match_id)
    assert match.status == MatchStatus.finished
    assert (match.home_penalties, match.away_penalties) == (4, 3)


async def test_league_shootout_gives_2_points_to_the_winner(
    session_factory, league_match
):
    league_id, match_id, home, away = league_match
    live = SimpleNamespace(
        match_id=match_id,
        task=asyncio.create_task(asyncio.sleep(0)),  # el runner ya terminó
        state=SimpleNamespace(home_score=1, away_score=1),
        shootout=SimpleNamespace(home_penalties=3, away_penalties=4, winner=Side.AWAY),
    )

    await MatchStarter(session_factory)._save_result(
        live, league_id=league_id, home_club_id=home, away_club_id=away
    )

    async with session_factory() as s:
        home_standing = await s.get(LeagueStandingsDB, (league_id, home))
        away_standing = await s.get(LeagueStandingsDB, (league_id, away))
    assert (away_standing.points, away_standing.won_penalties) == (2, 1)
    assert (home_standing.points, home_standing.lost) == (0, 1)
    # los penales no suman goles: solo el 1 a 1
    assert (home_standing.goals_for, home_standing.goals_against) == (1, 1)

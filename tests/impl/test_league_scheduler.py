import asyncio
import functools
import uuid

from sqlalchemy import select

from app.behaviors.defaults import DEFAULT_BEHAVIORS
from app.db.behavior import BehaviorDB
from app.db.club import ClubDB
from app.db.league import LeagueDB, LeagueEnrollmentDB, LeagueEnrollmentPlayerDB
from app.db.match import MatchDB, MatchStatus
from app.db.player import PlayerDB
from app.db.standings import LeagueStandingsDB
from app.db.user import UserDB
from app.repositories.league_repository import LeagueRepository
from app.ws.league_scheduler import LeagueScheduler
from app.ws.match import starter as starter_module
from app.ws.match.runner import live_matches, start_match
from app.ws.match.starter import MatchStarter


async def make_enrolled_club(session, league_id, name):
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

    enrollment_id = uuid.uuid4()
    session.add(
        LeagueEnrollmentDB(id=enrollment_id, league_id=league_id, club_id=club.id)
    )
    await session.flush()
    session.add_all(
        LeagueEnrollmentPlayerDB(
            id=uuid.uuid4(),
            enrollment_id=enrollment_id,
            player_id=p.id,
            is_starter=i < 3,
            behavior_id=behavior.id if i < 3 else None,
        )
        for i, p in enumerate(players)
    )
    return club.id


async def make_started_league(session, club_count=4):
    league_id = uuid.uuid4()
    club_ids = []
    for i in range(club_count):
        if i == 0:
            # creamos primero el club creador para la FK de leagues.creator_club_id
            user = UserDB(id=uuid.uuid4(), email="c0@x.com", hashed_password="h")
            session.add(user)
            await session.flush()
            creator = ClubDB(
                id=uuid.uuid4(),
                club_name="Club 0",
                avatar_url="https://x/0.png",
                user_id=user.id,
            )
            session.add(creator)
            await session.flush()
            session.add(
                LeagueDB(
                    id=league_id,
                    name="Liga Auto",
                    max_clubs=club_count,
                    match_duration_minutes=1,
                    status="not_started",
                    creator_club_id=creator.id,
                )
            )
            await session.flush()
            behavior = BehaviorDB(
                id=uuid.uuid4(),
                name="Atacante",
                code=DEFAULT_BEHAVIORS[0].code,
                club_id=creator.id,
            )
            players = [
                PlayerDB(
                    id=uuid.uuid4(),
                    name=f"J{j}",
                    number=j,
                    power=60,
                    agility=60,
                    control=60,
                    speed=60,
                    strength=60,
                    club_id=creator.id,
                )
                for j in range(1, 7)
            ]
            session.add_all([behavior, *players])
            await session.flush()
            enrollment_id = uuid.uuid4()
            session.add(
                LeagueEnrollmentDB(
                    id=enrollment_id, league_id=league_id, club_id=creator.id
                )
            )
            await session.flush()
            session.add_all(
                LeagueEnrollmentPlayerDB(
                    id=uuid.uuid4(),
                    enrollment_id=enrollment_id,
                    player_id=p.id,
                    is_starter=j < 3,
                    behavior_id=behavior.id if j < 3 else None,
                )
                for j, p in enumerate(players)
            )
            club_ids.append(creator.id)
        else:
            club_ids.append(
                await make_enrolled_club(session, league_id, f"Club {i}")
            )

    await session.commit()
    await LeagueRepository(session).start_league(league_id)
    return league_id, club_ids


async def test_rounds_wait_for_previous_round_to_finish(session, session_factory):
    league_id, _ = await make_started_league(session, club_count=4)

    started_by_call: list[uuid.UUID] = []
    round1_gate = asyncio.Event()
    round1_all_started = asyncio.Event()

    async with session_factory() as s:
        matches = (
            await s.execute(
                select(MatchDB)
                .where(MatchDB.league_id == league_id)
                .order_by(MatchDB.round_number)
            )
        ).scalars().all()
    round_by_match = {m.id: m.round_number for m in matches}

    class FakeStarter:
        async def start(self, match_id: uuid.UUID) -> asyncio.Task:
            started_by_call.append(match_id)
            if len(started_by_call) == 2:
                round1_all_started.set()

            async def _finish():
                if round_by_match[match_id] == 1:
                    await round1_gate.wait()

            return asyncio.create_task(_finish())

    scheduler = LeagueScheduler(
        session_factory=session_factory,
        starter=FakeStarter(),
        window_seconds=0,
    )
    task = scheduler.schedule(league_id)

    await round1_all_started.wait()
    # los 2 partidos de la fecha 1 arrancaron juntos, y ninguno de la fecha 2 arrancó todavía
    assert [round_by_match[m] for m in started_by_call] == [1, 1]

    round1_gate.set()
    await task

    assert [round_by_match[m] for m in started_by_call] == [1, 1, 2, 2, 3, 3]
    async with session_factory() as s:
        league = await s.get(LeagueDB, league_id)
    assert league.status == "finished"


async def test_league_scheduler_plays_all_rounds_and_finishes_league(
    session, session_factory, monkeypatch
):
    league_id, club_ids = await make_started_league(session, club_count=4)
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
    scheduler = LeagueScheduler(
        session_factory=session_factory,
        starter=starter,
        window_seconds=0,
    )

    try:
        await scheduler.schedule(league_id)

        async with session_factory() as s:
            league = await s.get(LeagueDB, league_id)
            matches = (
                await s.execute(
                    select(MatchDB).where(MatchDB.league_id == league_id)
                )
            ).scalars().all()
            standings = (
                await s.execute(
                    select(LeagueStandingsDB)
                    .where(LeagueStandingsDB.league_id == league_id)
                    .order_by(LeagueStandingsDB.rank)
                )
            ).scalars().all()

        assert league.status == "finished"
        assert len(matches) == 6
        assert all(m.status == MatchStatus.finished for m in matches)
        assert all(
            m.home_score is not None and m.away_score is not None for m in matches
        )

        assert [st.rank for st in standings] == [1, 2, 3, 4]
        assert all(st.matches_played == 3 for st in standings)
        assert all(
            st.points == 3 * st.won + st.drawn for st in standings
        )
        assert sum(st.goals_for for st in standings) == sum(
            st.goals_against for st in standings
        )
    finally:
        live_matches.clear()


async def test_league_scheduler_emits_ws_notifications_and_closes_lobby(
    session, session_factory
):
    league_id, _ = await make_started_league(session, club_count=4)

    events: list[tuple[str, uuid.UUID, dict | int]] = []

    class FakeLobby:
        async def broadcast(self, channel_id: uuid.UUID, message: dict) -> None:
            events.append(("broadcast", channel_id, message))

        async def close_all(self, channel_id: uuid.UUID, code: int = 1000) -> None:
            events.append(("close_all", channel_id, code))

    class FakeStarter:
        async def start(self, match_id: uuid.UUID) -> asyncio.Task:
            async def _finish():
                pass

            return asyncio.create_task(_finish())

    scheduler = LeagueScheduler(
        session_factory=session_factory,
        starter=FakeStarter(),
        lobby=FakeLobby(),
        window_seconds=0,
    )

    await scheduler.schedule(league_id)

    expected_updated = {
        "type": "leagueUpdated",
        "data": {"league_id": str(league_id)},
    }
    expected_finished = {
        "type": "leagueFinished",
        "data": {"league_id": str(league_id)},
    }

    # Verifico que se hayan enviado todos los eventos:
    # 3 fechas, 2 partidos por fecha -> por cada fecha:
    # 1 leagueUpdated (inicio espera) + 2 leagueUpdated (inicio partidos) + 2 leagueUpdated (fin partidos) = 5 por fecha -> 15 en total
    # + 1 leagueFinished + 1 close_all(1000)
    assert len(events) == 17
    for kind, channel_id, payload in events[:15]:
        assert kind == "broadcast"
        assert channel_id == league_id
        assert payload == expected_updated

    assert events[15] == ("broadcast", league_id, expected_finished)
    assert events[16] == ("close_all", league_id, 1000)

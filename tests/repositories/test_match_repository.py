import pytest
import uuid

from app.db.league import LeagueDB
from app.db.match import MatchDB, MatchStatus
from app.db.club import ClubDB
from app.db.user import UserDB
from app.repositories.match_repository import MatchRepository

async def test_create_save_match(session):
    # primero creamos los usuarios
    user_home_id = uuid.uuid4()
    user_home_db = UserDB(
        id=user_home_id,
        email="test1@example.com",
        hashed_password="password123"
    )
    user_away_id = uuid.uuid4()
    user_away_db = UserDB(
        id=user_away_id,
        email="test2@example.com",
        hashed_password="password123"
    )
    session.add(user_home_db)
    session.add(user_away_db)
    await session.commit()    

    # creamos los clubes
    home_club_id = uuid.uuid4()
    home_club = ClubDB(
        id=home_club_id,
        club_name="home",
        avatar_url="https://example.com/avatar.png",
        user_id=user_home_id
    )
    away_club_id = uuid.uuid4()
    away_club = ClubDB(
        id=away_club_id,
        club_name="away",
        avatar_url="https://example.com/avatar.png",
        user_id=user_away_id
    )
    session.add(home_club)
    session.add(away_club)
    await session.commit()

    repo = MatchRepository(session)
    match = await repo.create(
        home_club_id,
        away_club_id
    )
    # buscamos el partido que acabamos de crear
    match_db = await session.get(MatchDB, match.id)

    assert match_db is not None
    assert match_db.id == match.id
    assert match_db.home_club_id == home_club_id
    assert match_db.away_club_id == away_club_id


async def test_get_by_id_returns_match(session):
    # primero creamos los usuarios
    user_home_id = uuid.uuid4()
    user_home_db = UserDB(
        id=user_home_id,
        email="test1@example.com",
        hashed_password="password123"
    )
    user_away_id = uuid.uuid4()
    user_away_db = UserDB(
        id=user_away_id,
        email="test2@example.com",
        hashed_password="password123"
    )
    session.add(user_home_db)
    session.add(user_away_db)
    await session.commit()    

    # creamos los clubes
    home_club_id = uuid.uuid4()
    home_club = ClubDB(
        id=home_club_id,
        club_name="home",
        avatar_url="https://example.com/avatar.png",
        user_id=user_home_id
    )
    away_club_id = uuid.uuid4()
    away_club = ClubDB(
        id=away_club_id,
        club_name="away",
        avatar_url="https://example.com/avatar.png",
        user_id=user_away_id
    )
    session.add(home_club)
    session.add(away_club)
    await session.commit()

    # y creo el partido
    match_id = uuid.uuid4()
    match = MatchDB(
        id=match_id,
        home_club_id=home_club_id,
        away_club_id=away_club_id
    )
    session.add(match)
    await session.commit()

    consult_repo = MatchRepository(session)
    result = await consult_repo.get_by_id(match_id)

    assert result is not None
    assert result.id == match_id
    assert result.home_club_id == home_club_id
    assert result.home_club.club_name == "home"
    assert result.away_club_id == away_club_id
    assert result.away_club.club_name == "away"
    assert result.status == MatchStatus.scheduled
    assert result.league_id is None
    assert result.home_score is None
    assert result.away_score is None


async def test_get_by_id_returns_none(session):
    consult_repo = MatchRepository(session)
    result = await consult_repo.get_by_id(uuid.uuid4())
    
    assert result is None


async def test_list_by_league_orders_by_round_and_filters_by_status(session):
    u1, u2 = uuid.uuid4(), uuid.uuid4()
    session.add_all([
        UserDB(id=u1, email="u1@example.com", hashed_password="h"),
        UserDB(id=u2, email="u2@example.com", hashed_password="h"),
    ])
    await session.flush()

    c1, c2 = uuid.uuid4(), uuid.uuid4()
    session.add_all([
        ClubDB(id=c1, club_name="C1", avatar_url="https://x/1.png", user_id=u1),
        ClubDB(id=c2, club_name="C2", avatar_url="https://x/2.png", user_id=u2),
    ])
    await session.flush()

    league_id = uuid.uuid4()
    session.add(
        LeagueDB(
            id=league_id,
            name="Liga",
            max_clubs=4,
            match_duration_minutes=5,
            status="started",
            creator_club_id=c1,
        )
    )
    await session.flush()

    m_round_2 = MatchDB(
        id=uuid.uuid4(),
        home_club_id=c1,
        away_club_id=c2,
        league_id=league_id,
        round_number=2,
        status=MatchStatus.scheduled,
    )
    m_round_1 = MatchDB(
        id=uuid.uuid4(),
        home_club_id=c2,
        away_club_id=c1,
        league_id=league_id,
        round_number=1,
        status=MatchStatus.finished,
    )
    m_friendly = MatchDB(
        id=uuid.uuid4(),
        home_club_id=c1,
        away_club_id=c2,
    )
    session.add_all([m_round_2, m_round_1, m_friendly])
    await session.commit()

    repo = MatchRepository(session)
    all_matches = await repo.list_by_league(league_id)
    assert [m.id for m in all_matches] == [m_round_1.id, m_round_2.id]
    assert all_matches[0].home_club.club_name == "C2"
    assert all_matches[0].away_club.club_name == "C1"
    assert all_matches[1].home_club.club_name == "C1"
    assert all_matches[1].away_club.club_name == "C2"

    scheduled = await repo.list_by_league(league_id, status=MatchStatus.scheduled)
    assert [m.id for m in scheduled] == [m_round_2.id]
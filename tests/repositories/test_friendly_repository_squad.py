import uuid

from app.db.behavior import BehaviorDB
from app.db.club import ClubDB
from app.db.friendly import FriendlyDB, FriendlyPlayerDB
from app.db.match import MatchDB
from app.db.player import PlayerDB
from app.db.user import UserDB
from app.repositories.friendly_repository import FriendlyRepository


async def make_club(session, name):
    user = UserDB(id=uuid.uuid4(), email=f"{name}@x.com", hashed_password="h")
    session.add(user)
    await session.flush()
    club = ClubDB(id=uuid.uuid4(), club_name=name, avatar_url="a", user_id=user.id)
    session.add(club)
    await session.flush()
    behavior = BehaviorDB(id=uuid.uuid4(), name="b", code=f"code-{name}", club_id=club.id)
    session.add(behavior)
    await session.commit()
    return club.id, behavior.id


async def add_squad(session, friendly_id, club_id, behavior_id):
    """6 jugadores: titulares los números 4, 5 y 6 (con comportamiento).
    Los ids van al revés de los números, así el orden no sale de casualidad."""
    ids = sorted((uuid.uuid4() for _ in range(6)), reverse=True)
    players = [
        PlayerDB(id=ids[n - 1], name=f"J{n}", number=n, power=60, agility=60,
                 control=60, speed=60, strength=60, club_id=club_id)
        for n in range(1, 7)
    ]
    session.add_all(players)
    await session.flush()
    fp_ids = sorted((uuid.uuid4() for _ in range(6)), reverse=True)
    session.add_all(
        FriendlyPlayerDB(
            id=fp_ids[i], friendly_id=friendly_id, club_id=club_id, player_id=p.id,
            is_starter=p.number >= 4, behavior_id=behavior_id if p.number >= 4 else None,
        )
        for i, p in enumerate(players)
    )
    await session.commit()
    return [p.id for p in players]


async def test_get_squad_by_match(session):
    home, home_b = await make_club(session, "local")
    away, away_b = await make_club(session, "visita")
    match_id = uuid.uuid4()
    session.add(MatchDB(id=match_id, home_club_id=home, away_club_id=away))
    await session.flush()  # el partido antes que el amistoso (FK friendlies.match_id)
    friendly = FriendlyDB(id=uuid.uuid4(), creator_club_id=home, rival_club_id=away,
                          status="accepted", match_id=match_id)
    session.add(friendly)
    await session.commit()
    await add_squad(session, friendly.id, home, home_b)
    await add_squad(session, friendly.id, away, away_b)

    squad = await FriendlyRepository(session).get_squad_by_match(match_id)

    assert len(squad) == 12  # los suplentes también, aunque no tengan comportamiento
    home_squad = [m for m in squad if m.club_id == home]
    # primero los titulares (4, 5, 6) y después los suplentes, cada grupo por número
    assert [m.player.number for m in home_squad] == [4, 5, 6, 1, 2, 3]
    assert [m.is_starter for m in home_squad] == [True] * 3 + [False] * 3
    assert {m.behavior.code for m in home_squad[:3]} == {"code-local"}
    assert all(m.behavior is None for m in home_squad[3:])


async def test_get_squad_by_unknown_match_is_empty(session):
    assert await FriendlyRepository(session).get_squad_by_match(uuid.uuid4()) == []


async def test_get_formations_by_match(session):
    creator, _ = await make_club(session, "local")
    rival, _ = await make_club(session, "visita")
    repo = FriendlyRepository(session)

    friendly = await repo.create(creator, None, [], "OFFENSIVE_LINE")
    _, match = await repo.accept(friendly.id, rival, [], "DEFENSIVE_LINE")

    # el creador es el local y el rival el visitante
    assert await repo.get_formations_by_match(match.id) == (
        "OFFENSIVE_LINE",
        "DEFENSIVE_LINE",
    )

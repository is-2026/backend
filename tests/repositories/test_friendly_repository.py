import uuid

import pytest
from sqlalchemy import select

from app.db.club import ClubDB
from app.db.friendly import FriendlyDB, FriendlyPlayerDB
from app.db.player import PlayerDB
from app.db.user import UserDB
from app.repositories.friendly_repository import FriendlyRepository,InvalidSquad,SquadPlayerData



async def make_user(session) -> uuid.UUID:
    user_id = uuid.uuid4()
    user = UserDB(
        id=user_id, 
        email="moristeenmadrid@river912.com", 
        hashed_password="091218"
    )
    session.add(user)
    await session.flush()  # el usuario se inserta antes que el club

    club_id = uuid.uuid4()
    club =ClubDB(
            id=club_id,
            club_name="Club Atletico River Plate",
            avatar_url="https://JuanFernandoQuintero/avatar.png",
            user_id=user_id,
        )
    session.add(club)
    await session.commit()
    return club_id

async def make_players(session, club_id, n=6) -> list[uuid.UUID]:
    players = [
        PlayerDB(
            id=uuid.uuid4(),
            name=f"Jugador {ind}",
            number=ind + 1,
            power=100,
            agility=100,
            control=30,
            speed=30,
            strength=40,
            club_id=club_id,
        )
        for ind in range(n)
    ]
    session.add_all(players)
    await session.commit()
    return [p.id for p in players]

async def test_create_friendly_ok(session):
    club_id = await make_user(session)
    players = await make_players(session, club_id)
    squad = [SquadPlayerData(pid, i < 3, None) for i, pid in enumerate(players)]

    friendly = await FriendlyRepository(session).create(club_id, "hash", squad)

    assert friendly.id is not None
    assert friendly.creator_club_id == club_id
    assert friendly.hashed_password == "hash"

    assert await session.get(FriendlyDB, friendly.id) is not None

    result = await session.execute(
        select(FriendlyPlayerDB).where(FriendlyPlayerDB.friendly_id == friendly.id)
    )
    rows = result.scalars().all()  #Pido las filas que pertenezcan al amistoso
    assert len(rows) == 6  
    assert {r.player_id for r in rows} == set(players)
    assert sum(r.is_starter for r in rows) == 3
    assert all(r.club_id == club_id for r in rows)  #Todas las filas son del dueño del club


async def test_create_friendly_without_password(session):
    club_id = await make_user(session)
    players = await make_players(session, club_id, n=1)
    squad = [SquadPlayerData(players[0], True, None)]

    friendly = await FriendlyRepository(session).create(club_id, None, squad)

    assert friendly.hashed_password is None


async def test_create_friendly_nonexistent_player_raises(session):
    club_id = await make_user(session)
    squad = [SquadPlayerData(uuid.uuid4(), True, None)]  # jugador que no existe

    with pytest.raises(InvalidSquad):
        await FriendlyRepository(session).create(club_id, "hash", squad)


async def test_create_friendly_duplicate_player_raises(session):
    club_id = await make_user(session)
    players = await make_players(session, club_id, n=1)
    squad = [
        SquadPlayerData(players[0], True, None),
        SquadPlayerData(players[0], False, None),  # repetido
    ]

    with pytest.raises(InvalidSquad):
        await FriendlyRepository(session).create(club_id, "hash", squad)


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

    friendly = await FriendlyRepository(session).create(club_id, "hash", squad, "TRIANGLE")

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

    friendly = await FriendlyRepository(session).create(club_id, None, squad, "TRIANGLE")

    assert friendly.hashed_password is None


async def test_create_friendly_nonexistent_player_raises(session):
    club_id = await make_user(session)
    squad = [SquadPlayerData(uuid.uuid4(), True, None)]  # jugador que no existe

    with pytest.raises(InvalidSquad):
        await FriendlyRepository(session).create(club_id, "hash", squad, "TRIANGLE")


async def test_create_friendly_duplicate_player_raises(session):
    club_id = await make_user(session)
    players = await make_players(session, club_id, n=1)
    squad = [
        SquadPlayerData(players[0], True, None),
        SquadPlayerData(players[0], False, None),  # repetido
    ]

    with pytest.raises(InvalidSquad):
        await FriendlyRepository(session).create(club_id, "hash", squad, "TRIANGLE")


async def test_list_available_friendlies_empty(session):
    repo = FriendlyRepository(session)
    result = await repo.list_available_friendlies()
    assert result is not None
    assert result == []


async def test_list_available_friendlies_success(session):
    # creamos el usuario y su club
    user_id = uuid.uuid4()
    user_db = UserDB(
        id=user_id,
        email="test_friendly@example.com",
        hashed_password="password123"
    )
    session.add(user_db)
    await session.commit()
    club_id = uuid.uuid4()
    club_db = ClubDB(
        id=club_id,
        club_name="Club Test Amistosos",
        avatar_url="https://example.com/avatar.png",
        user_id=user_id
    )
    session.add(club_db)
    await session.commit()

    # creamos los amistosos para probar
    friendly_id_1 = uuid.uuid4()
    friendly_id_2 = uuid.uuid4()
    friendly_id_3 = uuid.uuid4()
    friendly_public = FriendlyDB(
        id=friendly_id_1,
        creator_club_id=club_id,
        status="waiting_for_rival",
        hashed_password=None    # amistoso publico
    )
    friendly_private = FriendlyDB(
        id=friendly_id_2,
        creator_club_id=club_id,
        status="waiting_for_rival",
        hashed_password="hashed" # amistoso privado
    )
    friendly_accepted = FriendlyDB(
        id=friendly_id_3,
        creator_club_id=club_id,
        status="accepted",  # status invalido (no deberia listarse)
        hashed_password=None
    )
    session.add(friendly_public)
    session.add(friendly_private)
    session.add(friendly_accepted)
    await session.commit()

    # hacemos la consulta
    repo = FriendlyRepository(session)
    result = await repo.list_available_friendlies()
    
    # aserciones
    assert result is not None
    assert isinstance(result, list)

    # solo 2 de los 3 amistosos cumplen con "waiting_for_rival"
    assert len(result) == 2
    assert isinstance(result[0], FriendlyDB)
    
    result_ids = [f.id for f in result]
    assert friendly_id_1 in result_ids
    assert friendly_id_2 in result_ids
    assert friendly_id_3 not in result_ids

    # verificamos la privacidad de los amistosos
    for friendly in result:
        if friendly.id == friendly_id_1:
            assert repo.is_private(friendly) is False
        elif friendly.id == friendly_id_2:
            assert repo.is_private(friendly) is True


async def test_get_club_names_only_requested_clubs(session):
    club_ids = {}
    for name in ("Boca", "River", "Racing"):
        user = UserDB(
            id=uuid.uuid4(), email=f"{name.lower()}@example.com", hashed_password="x"
        )
        session.add(user)
        await session.flush()  # el usuario se inserta antes que el club
        club = ClubDB(
            id=uuid.uuid4(),
            club_name=name,
            avatar_url="https://example.com/a.png",
            user_id=user.id,
        )
        session.add(club)
        club_ids[name] = club.id
    await session.commit()

    repo = FriendlyRepository(session)
    names = await repo.get_club_names([club_ids["Boca"], club_ids["River"]])

    assert names == {club_ids["Boca"]: "Boca", club_ids["River"]: "River"}

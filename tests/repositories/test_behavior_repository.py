import uuid

import pytest

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.db.behavior import BehaviorDB
from app.db.club import ClubDB
from app.db.user import UserDB
from app.repositories.behavior_repository import (
    BehaviorRepository,
    DuplicateNameBehavior,
)
from app.db.league import LeagueDB, LeagueEnrollmentDB, LeagueEnrollmentPlayerDB
from app.db.player import PlayerDB
from app.db.friendly import FriendlyDB, FriendlyPlayerDB
from app.db.match import MatchDB


# -- TESTS list_by_club --
async def test_list_by_club_exitoso(session):
    # 1. Creo primero el Usuario
    user_id = uuid.uuid4()
    user_db = UserDB(
        id=user_id, email="test@example.com", hashed_password="password123"
    )
    session.add(user_db)
    await session.commit()

    # 2. Creo el Club
    club_id = uuid.uuid4()
    club_db = ClubDB(
        id=club_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_id,
    )
    session.add(club_db)
    await session.commit()

    # pruebo club sin comportamientos
    consult_repo = BehaviorRepository(session)
    result = await consult_repo.list_by_club(club_id)
    assert result is not None
    assert result == []

    # 3. Creo varios comportamientos de prueba
    behavior_id1 = uuid.uuid4()
    behavior_id2 = uuid.uuid4()
    behavior_id3 = uuid.uuid4()

    behavior_db1 = BehaviorDB(
        id=behavior_id1,
        name="comportamiento1",
        code="def run(): running",
        club_id=club_id,
    )
    behavior_db2 = BehaviorDB(
        id=behavior_id2,
        name="comportamiento2",
        code="def run(): running",
        club_id=club_id,
    )
    behavior_db3 = BehaviorDB(
        id=behavior_id3,
        name="comportamiento3",
        code="def run(): running",
        club_id=club_id,
    )

    # pruebo club con comportamientos
    session.add(behavior_db1)
    session.add(behavior_db2)
    session.add(behavior_db3)
    await session.commit()

    result = await consult_repo.list_by_club(club_id)

    # compruebo que result sea list[BehaviorDB]
    assert result is not None
    assert isinstance(result, list)
    assert len(result) == 3
    assert isinstance(result[0], BehaviorDB)

    # comprueba que los comportamientos sean los correctos
    assert result[0].club_id == result[1].club_id == result[2].club_id == club_id
    assert result[0].id == behavior_id1
    assert result[1].id == behavior_id2
    assert result[2].id == behavior_id3


async def test_list_by_club_club_id_no_existe(session):
    consult_repo = BehaviorRepository(session)
    result = await consult_repo.list_by_club(uuid.uuid4())
    assert result == []


# -- TESTS get_id_and_club --
async def test_get_id_and_club_exitoso(session):
    # 1. Crear primero el Usuario (necesario por la FK user_id de ClubDB)
    user_id = uuid.uuid4()
    user_db = UserDB(
        id=user_id, email="test@example.com", hashed_password="password123"
    )
    session.add(user_db)
    await session.commit()

    # 2. Crear el Club usando los nombres exactos de sus columnas
    club_id = uuid.uuid4()
    club_db = ClubDB(
        id=club_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_id,
    )
    session.add(club_db)
    await session.commit()

    # creo un comportamiento falso
    behavior_id = uuid.uuid4()

    behavior_db = BehaviorDB(
        id=behavior_id, name="Correr", code="def run(): running", club_id=club_id
    )
    session.add(behavior_db)  # agrego el comportamiento a la sesion
    await session.commit()  # lo commiteo a la bd

    # consultamos al repositorio con el id y el clubid que cargamos
    consult_repo = BehaviorRepository(session)
    result = await consult_repo.get_id_and_club(behavior_id, club_id)

    assert result is not None
    assert result.id == behavior_id
    assert result.name == "Correr"
    assert result.code == "def run(): running"


async def test_get_id_and_club_id_no_existe(session):
    consult_repo = BehaviorRepository(session)
    result = await consult_repo.get_id_and_club(
        uuid.uuid4(), uuid.uuid4()
    )  # le pasamos 2 id cualquieras para q falle

    assert result is None


async def test_get_id_and_club_behavior_other_club(session):

    user_a_id = uuid.uuid4()
    user_a_db = UserDB(
        id=user_a_id, email="user_A@example.com", hashed_password="password123"
    )
    session.add(user_a_db)

    user_b_id = uuid.uuid4()
    user_b_db = UserDB(
        id=user_b_id, email="user_B@example.com", hashed_password="password123"
    )
    session.add(user_b_db)
    await session.commit()

    # club a
    club_a_id = uuid.uuid4()
    club_a_db = ClubDB(
        id=club_a_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_a_id,
    )
    session.add(club_a_db)

    # club b
    club_b_id = uuid.uuid4()
    club_b_db = ClubDB(
        id=club_b_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_b_id,
    )
    session.add(club_b_db)
    await session.commit()

    behavior_id = uuid.uuid4()
    behavior_db = BehaviorDB(
        id=behavior_id, name="Regate", code="def run(): pass", club_id=club_a_id
    )
    session.add(behavior_db)
    await session.commit()

    consult_repo = BehaviorRepository(session)
    result = await consult_repo.get_id_and_club(behavior_id, club_b_id)

    assert result is None


async def test_create_exitoso(session):
    user_id = uuid.uuid4()
    user_db = UserDB(
        id=user_id, email="test@example.com", hashed_password="password123"
    )
    session.add(user_db)
    await session.commit()

    # 2. Creo el Club
    club_id = uuid.uuid4()
    club_db = ClubDB(
        id=club_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_id,
    )
    session.add(club_db)
    await session.commit()

    consult_repo = BehaviorRepository(session)
    result = await consult_repo.create(
        club_db.id, "Pepito", "def run(): pass", "player"
    )
    assert result is not None
    assert result.id == result.id
    assert result.name == "Pepito"
    assert result.code == "def run(): pass"
    assert result.kind == "player"


async def test_create_name_use(session):
    user_id = uuid.uuid4()
    user_db = UserDB(
        id=user_id, email="test@example.com", hashed_password="password123"
    )
    session.add(user_db)
    await session.commit()

    # 2. Creo el Club
    club_id = uuid.uuid4()
    club_db = ClubDB(
        id=club_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_id,
    )
    session.add(club_db)
    await session.commit()

    consult_repo = BehaviorRepository(session)
    await consult_repo.create(
        club_db.id, "Atacante", "def run(): pass", "player"
    )  # creo primero 1
    with pytest.raises(DuplicateNameBehavior):
        await consult_repo.create(club_id, "Atacante", "def pasee(): pass", "player")


async def test_create_equal_name_2_club(session):

    user_a_id = uuid.uuid4()
    user_a_db = UserDB(
        id=user_a_id, email="user_A@example.com", hashed_password="password123"
    )
    session.add(user_a_db)

    user_b_id = uuid.uuid4()
    user_b_db = UserDB(
        id=user_b_id, email="user_B@example.com", hashed_password="password123"
    )
    session.add(user_b_db)
    await session.commit()

    # club a
    club_a_id = uuid.uuid4()
    club_a_db = ClubDB(
        id=club_a_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_a_id,
    )
    session.add(club_a_db)

    # club b
    club_b_id = uuid.uuid4()
    club_b_db = ClubDB(
        id=club_b_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_b_id,
    )
    session.add(club_b_db)
    await session.commit()

    consult_repo = BehaviorRepository(session)
    result = await consult_repo.create(
        club_a_db.id, "Pepito", "def run(): pass", "player"
    )
    assert result is not None
    assert result.id == result.id
    assert result.name == "Pepito"
    assert result.code == "def run(): pass"
    assert result.kind == "player"

    result_b = await consult_repo.create(
        club_b_db.id, "Pepito", "def run(): pass", "player"
    )
    assert result_b is not None
    assert result_b.id == result_b.id
    assert result_b.name == "Pepito"
    assert result_b.code == "def run(): pass"
    assert result_b.kind == "player"


async def test_update_succes(session):
    user_id = uuid.uuid4()
    user_db = UserDB(
        id=user_id, email="test@example.com", hashed_password="password123"
    )
    session.add(user_db)
    await session.commit()

    # 2. Creo el Club
    club_id = uuid.uuid4()
    club_db = ClubDB(
        id=club_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_id,
    )
    session.add(club_db)
    await session.flush()

    behavior_id = uuid.uuid4()
    behavior_db = BehaviorDB(
        id=behavior_id,
        name="Correr",
        code="def decide_action():\n pass",
        club_id=club_id,
        kind="player",
    )
    session.add(behavior_db)
    await session.commit()

    consult_repo = BehaviorRepository(session)
    result = await consult_repo.update(
        behavior_db.id, club_db.id, "Pepito", "def decide_action():\n x=912"
    )
    assert result is not None
    assert result.id == behavior_db.id
    assert result.name == "Pepito"
    assert result.code == "def decide_action():\n x=912"


async def test_update_none(session):
    user_id = uuid.uuid4()
    user_db = UserDB(
        id=user_id, email="test@example.com", hashed_password="password123"
    )
    session.add(user_db)
    await session.commit()

    # 2. Creo el Club
    club_id = uuid.uuid4()
    club_db = ClubDB(
        id=club_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_id,
    )
    session.add(club_db)
    await session.commit()

    behavior_id = uuid.uuid4()

    consult_repo = BehaviorRepository(session)
    result = await consult_repo.update(
        behavior_id, club_db.id, "Pepito", "def decide_action():\n x=912"
    )
    assert result == None


async def test_update_other_club(session):
    user_a_id = uuid.uuid4()
    user_a_db = UserDB(
        id=user_a_id, email="user_A@example.com", hashed_password="password123"
    )
    session.add(user_a_db)

    user_b_id = uuid.uuid4()
    user_b_db = UserDB(
        id=user_b_id, email="user_B@example.com", hashed_password="password123"
    )
    session.add(user_b_db)
    await session.commit()

    # club a
    club_a_id = uuid.uuid4()
    club_a_db = ClubDB(
        id=club_a_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_a_id,
    )
    session.add(club_a_db)

    # club b
    club_b_id = uuid.uuid4()
    club_b_db = ClubDB(
        id=club_b_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_b_id,
    )
    session.add(club_b_db)
    await session.flush()

    behavior_id = uuid.uuid4()
    behavior_db = BehaviorDB(
        id=behavior_id,
        name="Correr",
        code="def decide_action():\n pass",
        club_id=club_a_id,
        kind="player",
    )
    session.add(behavior_db)
    await session.commit()

    consult_repo = BehaviorRepository(session)
    result = await consult_repo.update(
        behavior_db.id, club_b_db.id, "Pepito", "def decide_action():\n x=912"
    )

    assert result == None


async def test_update_duplicate_name(session):
    user_a_id = uuid.uuid4()
    user_a_db = UserDB(
        id=user_a_id, email="user_A@example.com", hashed_password="password123"
    )
    session.add(user_a_db)
    await session.flush()

    # club
    club_id = uuid.uuid4()
    club_db = ClubDB(
        id=club_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_a_id,
    )
    session.add(club_db)
    await session.flush()

    behavior_a_id = uuid.uuid4()
    behavior_a_db = BehaviorDB(
        id=behavior_a_id,
        name="Correr",
        code="def decide_action():\n pass",
        club_id=club_db.id,
        kind="player",
    )
    session.add(behavior_a_db)

    behavior_b_id = uuid.uuid4()
    behavior_b_db = BehaviorDB(
        id=behavior_b_id,
        name="Dar Pase",
        code="def decide_action():\n pass",
        club_id=club_db.id,
        kind="player",
    )
    session.add(behavior_b_db)
    await session.commit()

    consult_repo = BehaviorRepository(session)
    with pytest.raises(DuplicateNameBehavior):
        await consult_repo.update(
            behavior_b_db.id, club_db.id, "Correr", "def decide_action():\n x=912"
        )

async def test_delete_player_succes(session):
    user_id = uuid.uuid4()
    user_db = UserDB(
        id=user_id, email="test@example.com", hashed_password="password123"
    )
    session.add(user_db)
    await session.commit()

    # 2. Creo el Club
    club_id = uuid.uuid4()
    club_db = ClubDB(
        id=club_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_id,
    )
    session.add(club_db)
    await session.flush()

    behavior_id = uuid.uuid4()
    behavior_db = BehaviorDB(
        id = behavior_id,
        name = "Correr",
        code = "def decide_action():\n pass",
        club_id = club_id,
        kind= "player"
    )
    session.add(behavior_db)
    await session.commit()

    consult_repo = BehaviorRepository(session)
    await consult_repo.delete(behavior_db)

    result = await session.scalar( ##Hago la consulta a ver si realmente delete lo hace
        select(BehaviorDB).where(BehaviorDB.id == behavior_id)
    )

    assert result is None

async def test_delete_behavior_coach_succes(session):
    user_id = uuid.uuid4()
    user_db = UserDB(
        id=user_id, email="test@example.com", hashed_password="password123"
    )
    session.add(user_db)
    await session.commit()

    # 2. Creo el Club
    club_id = uuid.uuid4()
    club_db = ClubDB(
        id=club_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_id,
    )
    session.add(club_db)
    await session.flush()

    behavior_id = uuid.uuid4()
    behavior_db = BehaviorDB(
        id = behavior_id,
        name = "Gagardo",
        code = "def decide_coach():\n pass",
        club_id = club_id,
        kind= "coach"
    )
    session.add(behavior_db)
    await session.commit()

    consult_repo = BehaviorRepository(session)
    await consult_repo.delete(behavior_db)

    result = await session.scalar( ##Hago la consulta a ver si realmente delete lo hace
        select(BehaviorDB).where(BehaviorDB.id == behavior_id)
    )

    assert result is None

@pytest.mark.parametrize(
    "status, expected",
    [
        ("not_started", True),
        ("started", True),
        ("finished", False),
        ("cancelled", False),
    ],
)
async def test_is_assigned_league_status(session, status, expected):
    user_id = uuid.uuid4()
    session.add(
        UserDB(id=user_id, email="moriste_en_madrid_912@example.com", hashed_password="09122018")
    )
    await session.commit()

    club_id = uuid.uuid4()
    session.add(
        ClubDB(
            id=club_id,
            club_name="River Plate",
            avatar_url="https://example.com/avatar.png",
            user_id=user_id,
        )
    )
    await session.commit()

    league_id = uuid.uuid4()
    session.add(
        LeagueDB(
            id=league_id,
            name="LPF",
            hashed_password=None,
            max_clubs=3,
            match_duration_minutes=5,
            status=status,
            creator_club_id=club_id,
        )
    )
    await session.commit()

    behavior_id = uuid.uuid4()
    session.add(
        BehaviorDB(
            id=behavior_id,
            name="Atacante",
            code="def decide_action():\n    pass",
            club_id=club_id,
            kind="player",
        )
    )
    await session.commit()

    player_id = uuid.uuid4()
    session.add(
        PlayerDB(  
            id=player_id,
            name="Cavegol",
            number=10,
            power=60,
            agility=60,
            control=60,
            speed=60,
            strength=60,
            club_id=club_id,
        )
    )
    await session.commit()

    enrollment_id = uuid.uuid4()
    session.add(
        LeagueEnrollmentDB( 
            id=enrollment_id,
            league_id=league_id,
            club_id=club_id,
        )
    )
    await session.commit()

    session.add(
        LeagueEnrollmentPlayerDB(
            id=uuid.uuid4(),
            enrollment_id=enrollment_id,
            player_id=player_id,
            is_starter=True,
            behavior_id=behavior_id,
        )
    )
    await session.commit()

    consult_repo = BehaviorRepository(session)
    result = await consult_repo.is_assigned(behavior_id)
    assert result is expected


@pytest.mark.parametrize(
    "friendly_status, match_status, expected",
    [
        ("waiting_for_rival", None, True),
        ("accepted", "in_progress", True),
        ("accepted", "finished", False),
        ("cancelled", None, False),
    ],
)
async def test_is_assigned_friendly_status(
    session, friendly_status, match_status, expected
):
    user_id = uuid.uuid4()
    session.add(
        UserDB(id=user_id, email="moriste_en_madrid_912@example.com", hashed_password="09122018")
    )
    await session.commit()

    club_id = uuid.uuid4()
    session.add(
        ClubDB(
            id=club_id,
            club_name="River Plate",
            avatar_url="https://example.com/avatar.png",
            user_id=user_id,
        )
    )
    await session.commit()

    behavior_id = uuid.uuid4()
    session.add(
        BehaviorDB(
            id=behavior_id,
            name="Atacante",
            code="def decide_action():\n    pass",
            club_id=club_id,
            kind="player",
        )
    )
    await session.commit()

    player_id = uuid.uuid4()
    session.add(
        PlayerDB( 
            id=player_id,
            name="CaveGOL",
            number=10,
            power=60,
            agility=60,
            control=60,
            speed=60,
            strength=60,
            club_id=club_id,
        )
    )
    await session.commit()

    match_id = None
    if match_status is not None:
        match_id = uuid.uuid4()
        session.add(
            MatchDB(
                id=match_id,
                home_club_id=club_id,
                away_club_id=club_id,
                status=match_status,
            )
        )
        await session.commit()

    friendly_id = uuid.uuid4()
    session.add(
        FriendlyDB(
            id=friendly_id,
            creator_club_id=club_id,
            status=friendly_status,
            match_id=match_id,
        )
    )
    await session.commit()

    session.add(
        FriendlyPlayerDB(
            id=uuid.uuid4(),
            friendly_id=friendly_id,
            club_id=club_id,
            player_id=player_id,
            is_starter=True,
            behavior_id=behavior_id,
        )
    )
    await session.commit()

    result = await BehaviorRepository(session).is_assigned(behavior_id)
    assert result is expected

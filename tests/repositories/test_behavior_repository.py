import pytest
import uuid

from app.db.behavior import BehaviorDB
from app.db.club import ClubDB
from app.db.user import UserDB
from app.repositories.behavior_repository import BehaviorRepository

async def test_get_id_and_club_exitoso(session):
   # 1. Crear primero el Usuario (necesario por la FK user_id de ClubDB)
    user_id = uuid.uuid4()
    user_db = UserDB(
        id=user_id,
        email="test@example.com",
        hashed_password="password123"
    )
    session.add(user_db)
    await session.commit()

    # 2. Crear el Club usando los nombres exactos de sus columnas
    club_id = uuid.uuid4()
    club_db = ClubDB(
        id=club_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_id
    )
    session.add(club_db)
    await session.commit()

    #creo un comportamiento falso
    behavior_id = uuid.uuid4()
    
    behavior_db = BehaviorDB(
        id = behavior_id,
        name= "Correr",
        code= "def run(): running",
        club_id= club_id
    )
    session.add(behavior_db) #agrego el comportamiento a la sesion
    await session.commit() # lo commiteo a la bd

    #consultamos al repositorio con el id y el clubid que cargamos
    consult_repo = BehaviorRepository(session)
    result = await consult_repo.get_id_and_club(behavior_id, club_id)

    assert result is not None
    assert result.id == behavior_id
    assert result.name == "Correr"
    assert result.code == "def run(): running"


async def test_get_id_and_club_id_no_existe(session):
    consult_repo = BehaviorRepository(session)
    result = await consult_repo.get_id_and_club(uuid.uuid4(), uuid.uuid4()) #le pasamos 2 id cualquieras para q falle

    assert result is None

async def test_get_id_and_club_behavior_other_club(session):

    user_a_id = uuid.uuid4()
    user_a_db = UserDB(
        id=user_a_id,
        email="user_A@example.com",
        hashed_password="password123"
    )
    session.add(user_a_db)
    
    user_b_id = uuid.uuid4()
    user_b_db = UserDB(
        id=user_b_id,
        email="user_B@example.com",
        hashed_password="password123"
    )
    session.add(user_b_db)
    await session.commit()
        
        
    #club a 
    club_a_id = uuid.uuid4()
    club_a_db = ClubDB(
        id=club_a_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_a_id
    )
    session.add(club_a_db)

    #club b
    club_b_id = uuid.uuid4()
    club_b_db = ClubDB(
        id= club_b_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=user_b_id
    )
    session.add(club_b_db)
    await session.commit()

    behavior_id = uuid.uuid4()
    behavior_db = BehaviorDB(
        id= behavior_id,
        name="Regate",
        code="def run(): pass",
        club_id= club_a_id
    )
    session.add(behavior_db)
    await session.commit()


    consult_repo = BehaviorRepository(session)
    result = await consult_repo.get_id_and_club( behavior_id, club_b_id)

    assert result is None
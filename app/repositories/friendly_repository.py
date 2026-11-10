import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import NamedTuple

from app.db.behavior import BehaviorDB
from app.db.club import ClubDB
from app.db.friendly import FriendlyDB, FriendlyPlayerDB
from app.db.match import MatchDB
from app.db.player import PlayerDB


class SquadPlayerData(NamedTuple):
    player_id : uuid.UUID
    is_starter : bool
    behavior_id : uuid.UUID | None


class SquadMember(NamedTuple):
    club_id: uuid.UUID
    player: PlayerDB
    is_starter: bool
    behavior: BehaviorDB | None  # los suplentes no tienen comportamientos


class InvalidSquad(Exception):
    """La convocatoria no es valida (jugadores repetidos/inexistentes)"""


class FriendlyUnavailable(Exception):
    """El amistoso ya tiene rival o fue cancelado"""


class FriendlyRepository:
    def __init__(self, session : AsyncSession) -> None:
        self._session = session

    def is_private(self, friendly: FriendlyDB) -> bool:
        # true si hay una contraseña guardada, false si es None
        return bool(friendly.hashed_password)

    async def list_available_friendlies(
        self, club_name: str | None = None
    ) -> list[FriendlyDB]:
        consult = select(FriendlyDB).where(FriendlyDB.status == "waiting_for_rival")
        # si llego un club_name, lo usamos para buscar (join con clubs)
        # ojo: ILIKE de SQL hace pattern matching con la palabra completa (case insensitive).
        # si club_name="boca", "boca unidos" matchea, "bocado club" no.
        if club_name is not None:
            consult = consult.join(
                ClubDB, FriendlyDB.creator_club_id == ClubDB.id
            ).where(ClubDB.club_name.ilike(f"%{club_name}%"))
        result = await self._session.execute(consult)
        return list(result.scalars().all())

    async def create(
                    self,
                    creator_club_id: uuid.UUID,
                    hashed_password : str | None,
                    players: list[SquadPlayerData],
                    formation: str,
                    )-> FriendlyDB:
        friendly = FriendlyDB(
                            id=uuid.uuid4(),
                            creator_club_id= creator_club_id,
                            hashed_password = hashed_password,
                            creator_formation=formation,
                            )
        self._session.add(friendly)
        await self._session.flush() #hago flush para q exista el friendly.id antes de crear jugadores

        players_list=[
            FriendlyPlayerDB(
                id = uuid.uuid4(),
                friendly_id= friendly.id,
                club_id= creator_club_id,
                player_id= player.player_id,
                is_starter= player.is_starter,
                behavior_id= player.behavior_id
            )
            for player in players
        ]
        self._session.add_all(players_list)
        try:
            await self._session.commit()
        except IntegrityError as exc_info:
            await self._session.rollback()
            raise InvalidSquad() from exc_info

        await self._session.refresh(friendly)
        return friendly

    async def get(self, friendly_id: uuid.UUID) -> FriendlyDB | None:
        return await self._session.get(FriendlyDB, friendly_id)

    async def get_club_name(self, club_id: uuid.UUID) -> str | None:
        result = await self._session.execute(
            select(ClubDB.club_name).where(ClubDB.id == club_id)
        )
        return result.scalar_one_or_none()

    async def get_club_names(self, club_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        # una sola consulta para todos los clubes, en vez de una por amistoso
        result = await self._session.execute(
            select(ClubDB.id, ClubDB.club_name).where(ClubDB.id.in_(club_ids))
        )
        return dict(result.all())

    async def accept(
                    self,
                    friendly_id: uuid.UUID,
                    rival_club_id: uuid.UUID,
                    players: list[SquadPlayerData],
                    formation: str,
                    ) -> tuple[FriendlyDB, MatchDB]:
        result = await self._session.execute(
            select(FriendlyDB)
            .where(FriendlyDB.id == friendly_id)
            .with_for_update()
            .execution_options(populate_existing=True)  # lee el estado real, no el que ya tenía la sesión
        )
        friendly = result.scalar_one_or_none()
        if friendly is None or friendly.status != "waiting_for_rival":
            await self._session.rollback()
            raise FriendlyUnavailable()

        match = MatchDB(
            id=uuid.uuid4(),
            home_club_id=friendly.creator_club_id,
            away_club_id=rival_club_id,
        )
        self._session.add(match)
        await self._session.flush()  # el partido tiene que existir antes de setear friendly.match_id (FK)

        friendly.rival_club_id = rival_club_id
        friendly.rival_formation = formation
        friendly.status = "accepted"
        friendly.match_id = match.id

        self._session.add_all([
            FriendlyPlayerDB(
                id=uuid.uuid4(),
                friendly_id=friendly.id,
                club_id=rival_club_id,
                player_id=player.player_id,
                is_starter=player.is_starter,
                behavior_id=player.behavior_id,
            )
            for player in players
        ])
        try:
            await self._session.commit()
        except IntegrityError as exc_info:
            await self._session.rollback()
            raise InvalidSquad() from exc_info

        await self._session.refresh(friendly)
        await self._session.refresh(match)
        return friendly, match

    async def get_squad_by_match(self, match_id: uuid.UUID) -> list[SquadMember]:
        """Los convocados de los dos clubes del amistoso de ese partido:
        primero los titulares, y dentro de cada grupo por número de camiseta."""
        result = await self._session.execute(
            select(FriendlyPlayerDB.club_id, PlayerDB, FriendlyPlayerDB.is_starter, BehaviorDB)
            .join(FriendlyDB, FriendlyDB.id == FriendlyPlayerDB.friendly_id)
            .join(PlayerDB, PlayerDB.id == FriendlyPlayerDB.player_id)
            .outerjoin(BehaviorDB, BehaviorDB.id == FriendlyPlayerDB.behavior_id)  # LEFT JOIN: los suplentes no tienen comportamiento
            .where(FriendlyDB.match_id == match_id)
            .order_by(FriendlyPlayerDB.is_starter.desc(), PlayerDB.number)
        )
        return [SquadMember(*row) for row in result.all()]

    async def get_formations_by_match(self, match_id: uuid.UUID) -> tuple[str, str]:
        """(formación del local, formación del visitante) del amistoso de ese partido.
        El creador es el local y el rival el visitante (ver accept)."""
        result = await self._session.execute(
            select(FriendlyDB.creator_formation, FriendlyDB.rival_formation)
            .where(FriendlyDB.match_id == match_id)
        )
        row = result.one()
        return row.creator_formation, row.rival_formation

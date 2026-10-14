import uuid

from fastapi import HTTPException, status

from app.apis.leagues_api_base import BaseLeaguesApi
from app.impl.friendlies_api_impl import _validate_squad
from app.db.club import ClubDB
from app.db.session import SessionLocal
from app.models.join_league_input import JoinLeagueInput
from app.models.create_league_input import CreateLeagueInput
from app.models.league_detail import LeagueDetail
from app.repositories.league_repository import (
    LeagueRepository,
    SquadPlayerData,
    ClubAlreadyEnrolled,
)
from app.repositories.player_repository import PlayerRepository
from app.db.behavior import BehaviorDB
from app.security.passwords import hash_password, verify_password
from app.ws.lobby_league import league_lobby_connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

MAX_CLUBS_LIMIT = 20
MIN_CLUBS = 3
SQUAD_SIZE = 6
STARTERS = 3


def _validate_league(data: CreateLeagueInput) -> None:
    if not MIN_CLUBS <= data.max_clubs <= MAX_CLUBS_LIMIT:
        raise HTTPException(
            status_code=400,
            detail="max_clubs debe estar entre 3 y 20",
        )
    if len(data.players) != SQUAD_SIZE:
        raise HTTPException(400, "Se requieren exactamente 6 jugadores")

    starters = [p for p in data.players if p.is_starter]
    if len(starters) != STARTERS:
        raise HTTPException(400, "Se requieren exactamente 3 titulares")

    if len({p.player_id for p in data.players}) != SQUAD_SIZE:
        raise HTTPException(400, "Hay jugadores repetidos")

    if any(p.behavior_id is None for p in starters):
        raise HTTPException(400, "Cada titular debe tener un comportamiento asignado")


class LeaguesApiImpl(BaseLeaguesApi):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_league(
        self, create_league_input: CreateLeagueInput, club_id: ClubDB
    ) -> LeagueDetail:
        _validate_league(create_league_input)

        player_ids = [pl.player_id for pl in create_league_input.players]
        owned = await PlayerRepository(self._session).count_club_players(
            club_id.id, player_ids
        )
        if owned != SQUAD_SIZE:
            raise HTTPException(
                status_code=400, detail="Hay jugadores que no pertenecen a tu club"
            )

        for pl in create_league_input.players:
            if pl.is_starter:
                behavior = await self._session.get(BehaviorDB, pl.behavior_id)
                if behavior is None or behavior.club_id != club_id.id:
                    raise HTTPException(
                        status_code=400,
                        detail="Hay comportamientos que no pertenecen a tu club",
                    )

        hashed = (
            await hash_password(create_league_input.password)
            if create_league_input.password
            else None
        )

        try:
            league = await LeagueRepository(self._session).create_with_enrollment(
                name=create_league_input.name,
                hashed_password=hashed,
                max_clubs=create_league_input.max_clubs,
                match_duration_minutes=create_league_input.match_duration_minutes,
                club_id=club_id.id,
                squadPlayer=[
                    SquadPlayerData(pl.player_id, pl.is_starter, pl.behavior_id)
                    for pl in create_league_input.players
                ],
            )
        except IntegrityError as exc_info:
            raise HTTPException(
                status_code=400, detail="Datos de la liga invalidos"
            ) from exc_info

        return LeagueDetail(
            id=league.id,
            name=league.name,
            is_private=league.hashed_password is not None,
            max_clubs=league.max_clubs,
            status=league.status,
            registered_clubs=[{"club_id": club_id.id, "club_name": club_id.club_name}],
        )

    async def list_leagues(self) -> list[LeagueDetail]:
        repo = LeagueRepository(self._session)
        leagues = await repo.list_not_started()

        result = []
        for league in leagues:
            clubs = await repo.list_clubs_of_league(league.id)

            registered = []
            for club in clubs:
                registered.append({"club_id": club.id, "club_name": club.club_name})

            result.append(
                LeagueDetail(
                    id=league.id,
                    name=league.name,
                    is_private=league.hashed_password is not None,
                    max_clubs=league.max_clubs,
                    status=league.status,
                    registered_clubs=registered,
                )
            )
        return result

    async def get_league(self, league_id: uuid.UUID) -> LeagueDetail:
        repoliga = LeagueRepository(self._session)

        league = await repoliga.get(league_id)  # Busco la liga por id
        if league is None or league.status != "not_started":
            raise HTTPException(status_code=404, detail="La liga no existe")

        clubs = await repoliga.list_clubs_of_league(league.id)

        registered = []
        for club in clubs:
            registered.append(
                {"club_id": club.id, "club_name": club.club_name}
            )  # el append es para agregar cosas a la lista

        return LeagueDetail(
            id=league.id,
            name=league.name,
            is_private=league.hashed_password is not None,
            max_clubs=league.max_clubs,
            status=league.status,
            registered_clubs=registered,
        )

    async def join_league(
        self,
        league_id: uuid.UUID,
        join_league_input: JoinLeagueInput,
        club: ClubDB,
    ) -> None:
        repo = LeagueRepository(self._session)

        # valido el equipo (error 400)
        _validate_squad(join_league_input.players)

        league = await repo.get(league_id)  # obtengo la liga

        # valido la existencia de la liga (error 404)
        if not league:
            raise HTTPException(status_code=404, detail="La liga no existe")

        # verifico si la liga es privada y valido (error 400)
        if league.hashed_password:
            if not join_league_input.password or not await verify_password(
                join_league_input.password, league.hashed_password
            ):
                raise HTTPException(status_code=400, detail="Contraseña incorrecta")

        # verifico si hay cupo (error 400)
        enrolled_clubs = await repo.list_clubs_of_league(league_id)
        if len(enrolled_clubs) >= league.max_clubs:
            raise HTTPException(
                status_code=400, detail="No hay cupo disponible para la liga"
            )

        # mapeo los jugadores de SquadPlayerInput a SquadPlayerData
        data_players = [
            SquadPlayerData(
                player_id=pl.player_id,
                is_starter=pl.is_starter,
                behavior_id=pl.behavior_id,
            )
            for pl in join_league_input.players
        ]

        # inscribo al club
        try:
            await repo.add_enrollment(
                league_id=league_id, club_id=club.id, squadPlayer=data_players
            )
        except ClubAlreadyEnrolled:
            # club ya inscripto (error 409)
            raise HTTPException(
                status_code=409, detail="El club ya está inscripto en esta liga"
            )

        # tras la inscripcion del club, armo el evento ClubRegistered y lo transmito por el lobby de la liga
        event_club_registered = {
            "type": "ClubRegistered",
            "payload": {
                "league_id": str(league_id),
                "club_id": str(club.id),
                "club_name": club.club_name,
                "registered_count": len(enrolled_clubs)
                + 1,  # aumentamos en 1 la cantidad total de inscriptos
            },
        }

        await league_lobby_connection.broadcast(league_id, event_club_registered)
        return

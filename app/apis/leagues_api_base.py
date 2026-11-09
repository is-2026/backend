# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from pydantic import field_validator
from typing import Any, List, Optional
from uuid import UUID
from app.models.create_league_input import CreateLeagueInput
from app.models.error import Error
from app.models.join_league_input import JoinLeagueInput
from app.models.league_detail import LeagueDetail
from app.models.league_summary import LeagueSummary
from app.models.match import Match
from app.models.standings_item import StandingsItem
from app.models.submit_lineup_input import SubmitLineupInput
from app.security_api import get_token_bearerAuth

class BaseLeaguesApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseLeaguesApi.subclasses = BaseLeaguesApi.subclasses + (cls,)
    async def list_leagues(
        self,
    ) -> List[LeagueDetail]:
        """Devuelve tanto ligas públicas como privadas. Solo no iniciadas"""
        ...


    async def create_league(
        self,
        create_league_input: CreateLeagueInput,
        club_id : UUID
    ) -> LeagueDetail:
        """Notar que la cantidad de clubes tiene un mínimo duro de 3. Si se envía password, la liga se considera privada."""
        ...


    async def list_my_leagues(
        self,
        club_id : UUID,
    ) -> List[LeagueSummary]:
        """Identifica al club mediante el token de sesión. Devuelve las ligas en las que el club está inscripto."""
        ...


    async def get_league(
        self,
        league_id: UUID,
    ) -> LeagueDetail:
        ...


    async def cancel_league(
        self,
        league_id: UUID,
    ) -> None:
        """Solo el creador puede cancelarla, y solo si no está iniciada."""
        ...


    async def join_league(
        self,
        league_id: UUID,
        join_league_input: JoinLeagueInput,
        club_id: UUID,
    ) -> None:
        """Reserva un cupo para la liga. Se definen 6 jugadores convocados para toda la liga (3 marcados como titulares por defecto, 3 como suplentes). Los titulares enviados se usan como fallback si el club no define la alineación antes de alguno de sus partidos."""
        ...


    async def leave_league(
        self,
        league_id: UUID,
        club_id: UUID,
    ) -> None:
        ...


    async def start_league(
        self,
        league_id: UUID,
        club_id: UUID,
    ) -> LeagueDetail:
        """Solo el creador puede iniciarla. Cambia el estado a started y genera el fixture."""
        ...


    async def list_league_matches(
        self,
        league_id: UUID,
        status: Optional[str],
    ) -> List[Match]:
        ...


    async def get_standings(
        self,
        league_id: UUID,
    ) -> List[StandingsItem]:
        ...


    async def get_league_lineup(
        self,
        league_id: UUID,
        club_id: UUID,
    ) -> SubmitLineupInput:
        """Devuelve la alineacion vigente del club de la liga."""
        ...


    async def update_league_lineup(
        self,
        league_id: UUID,
        submit_lineup_input: SubmitLineupInput,
        club_id: UUID,
    ) -> SubmitLineupInput:
        """Guarda la alineacion del club en la liga. Rige desde el proximo partido."""
        ...
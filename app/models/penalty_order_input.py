from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field


class PenaltyKickerInput(BaseModel):
    player_id: UUID
    behavior_id: UUID


class PenaltyOrderInput(BaseModel):
    """Los 5 pateadores en orden, sin repetir, elegidos entre los 6 convocados del club.
    """

    kickers: Annotated[list[PenaltyKickerInput], Field(min_length=5, max_length=5)]

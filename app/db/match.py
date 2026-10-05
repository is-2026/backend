import uuid, enum

from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # solo para el type checker: importarlo de verdad arma un ciclo con club -> base -> match
    from app.db.club import ClubDB


class MatchStatus(str, enum.Enum):
    scheduled = "scheduled"
    in_progress = "in_progress"
    paused = "paused"
    finished = "finished"

class MatchDB(Base):
    __tablename__ = "matches"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    home_club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id"),
        nullable=False
        )
    away_club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id"),
        nullable=False
        )
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus), 
        default=MatchStatus.scheduled
        )
    home_score: Mapped[int | None]
    away_score: Mapped[int | None]

    # por ahora todos los partidos tienen league_id=none
    league_id: Mapped[uuid.UUID | None] = mapped_column(
        #ForeignKey("leagues.id"),
        default=None
        )

    # RELATIONSHIPS --
    # 1 partido tiene 1 club local
    home_club: Mapped[ClubDB] = relationship(
        foreign_keys=[home_club_id], 
        back_populates="home_matches"
    )
    # 1 partido tiene 1 club visitante
    away_club: Mapped[ClubDB] = relationship(
        foreign_keys=[away_club_id], 
        back_populates="away_matches"
    )
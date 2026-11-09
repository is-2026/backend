import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Integer, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LeagueDB(Base):
    __tablename__ = "leagues"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_clubs: Mapped[int] = mapped_column(Integer, nullable=False)
    match_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="not_started"
    )
    creator_club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LeagueEnrollmentDB(Base):  # tabla para los clubes que se inscriben
    __tablename__ = "league_enrollments"
    __table_args__ = (UniqueConstraint(
        "league_id", "club_id"
    ),)  # el club se inscribe solo 1 vez por liga

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, index=True
    )
    league_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leagues.id"), nullable=False
    )
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id"), nullable=False)
    formation: Mapped[str] = mapped_column(
        String(20), nullable = False, default="TRIANGLE", server_default="TRIANGLE"
    )   # formación con la que juega el club en la liga


class LeagueEnrollmentPlayerDB(Base):  # tabla para los jugadores del club
    __tablename__ = "league_enrollment_players"
    __table_args__ = (UniqueConstraint("enrollment_id", "player_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, index=True
    )
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("league_enrollments.id"), nullable=False
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("players.id"), nullable=False
    )
    is_starter: Mapped[bool] = mapped_column(nullable=False)
    behavior_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("behaviors.id", ondelete = "SET NULL"), nullable=True
    )  # solo titulares

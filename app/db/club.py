import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class ClubDB(Base):
    __tablename__ = "clubs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, index=True
    )
    club_name: Mapped[str] = mapped_column(String(50), nullable=False)
    avatar_url: Mapped[str] = mapped_column(String(512), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # RELATIONSHIPS --
    # 1 club juega muchos partidos de local
    home_matches: Mapped[list["MatchDB"]] = relationship(
        foreign_keys="[MatchDB.home_club_id]", back_populates="home_club"
    )
    # 1 club juega muchos partidos de visitante
    away_matches: Mapped[list["MatchDB"]] = relationship(
        foreign_keys="[MatchDB.away_club_id]", back_populates="away_club"
    )
    coach_behavior_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "behaviors.id",
            ondelete="SET NULL",
            name="fk_clubs_coach_behavior_id",
            use_alter=True,
        ),
        nullable=True,
    )

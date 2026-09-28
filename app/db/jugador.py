#tipos necesarios para SQLalchemy
from sqlalchemy import Column, Integer, String, ForeignKey 
from sqlalchemy.orm import Mapped, mapped_column

#base declarativa creada en base.py
from app.db.base import Base 

import uuid

class Jugador(Base):
    __tablename__ = "jugadores"

    #el Mapped aclara el entorno, en este caso uuid (Identificador unico universal)
    id: Mapped[uuid.UUID]      = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    nombre                     = Column(String(50), nullable=False)
    numero                     = Column(Integer, nullable=False, unique=True) #el numero de camiseta debe ser unico
    #PACSS
    power                      = Column(Integer, nullable=False)
    agility                    = Column(Integer, nullable=False)
    control                    = Column(Integer, nullable=False)
    speed                      = Column(Integer, nullable=False)
    strength                   = Column(Integer, nullable=False)

    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubes.id"), nullable= False)

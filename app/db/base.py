from sqlalchemy.orm import DeclarativeBase
 
 
class Base(DeclarativeBase):
    """Base declarativa de la que heredan todas las entidades ORM."""

import app.db.player  # noqa
import app.db.user  # noqa

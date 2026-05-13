"""
SquadMind – SQLAlchemy Declarative Base
All models inherit from Base.  Import models here so Alembic can detect them.
"""

from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    """
    Common base for all ORM models.
    - table name auto-derived from class name (snake_case pluralised)
    - provides __repr__ for debugging
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805
        # Convert CamelCase → snake_case and pluralise
        import re
        name = re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower()
        # Simple pluralisation (add 's' or 'es')
        return name + "s" if not name.endswith("s") else name + "es"

    def __repr__(self) -> str:  # pragma: no cover
        cols = ", ".join(
            f"{c.name}={getattr(self, c.name)!r}"
            for c in self.__table__.columns
            if c.name in ("id", "email", "status")
        )
        return f"<{self.__class__.__name__}({cols})>"

# ── Import all models here so Alembic autogenerate sees them ─────────────────

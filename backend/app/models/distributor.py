"""
Distributeur (revendeur / commercial) — section 39 du cahier des charges.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import CHAR, TypeDecorator

from app.core.database import Base


class GUID(TypeDecorator):
    """UUID portable : natif sur Postgres, CHAR(36) sur SQLite (dev/tests)."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return uuid.UUID(str(value))


class Distributor(Base):
    __tablename__ = "distributors"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    country = Column(String, nullable=True)
    commission_rate = Column(Float, default=10.0)  # en pourcentage
    status = Column(String, default="active")  # active | suspended
    created_at = Column(DateTime, default=datetime.utcnow)

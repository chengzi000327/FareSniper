from pathlib import Path

from backend.db.models import Base as ExistingBase
from backend.db.session import AsyncSessionLocal, engine as existing_engine
from backend.infrastructure.db.base import Base, SessionLocal, engine


def test_infrastructure_db_base_bridges_existing_base():
    assert Base is ExistingBase
    assert engine is existing_engine
    assert SessionLocal is AsyncSessionLocal


def test_alembic_uses_existing_migrations_path_only():
    assert Path("backend/db/migrations/env.py").exists()
    assert not Path("backend/migrations").exists()
    assert (
        "script_location = %(here)s/db/migrations"
        in Path("backend/alembic.ini").read_text()
    )

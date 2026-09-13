from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# Single canonical Base — all models must import from here.
Base = declarative_base()

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=not settings.DATABASE_URL.startswith("sqlite"),
)

# Auto-create tables for local SQLite development.
# Models must already be imported (via app.models) before this runs.
# The conditional import is deferred to avoid circular imports at module load time.
if settings.DATABASE_URL.startswith("sqlite"):
    from app.models import (  # noqa: F401 — side-effect: registers tables on Base
        organization, role, user, agent, tool, permission,
        policy, budget, tool_request, hitl_request, audit_log, api_key
    )
    Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

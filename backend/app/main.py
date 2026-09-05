from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agents import router as agents_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.guard import router as guard_router
from app.api.hitl import router as hitl_router
from app.api.permissions import router as permissions_router
from app.api.tools import router as tools_router
from app.core.config import settings

app = FastAPI(
    title="AgentGuard Core Engine",
    description="Framework-Agnostic Runtime Governance Layer for Autonomous AI Agents",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(tools_router, prefix="/api/v1")
app.include_router(permissions_router, prefix="/api/v1")
app.include_router(guard_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(hitl_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/ready")
def readiness_check():
    return {"status": "ready"}

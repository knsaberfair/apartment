from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import APP_ENV
from app.database import get_connection, init_db
from app.routers import audit, auth, contracts, dashboard, finance, maintenance, permissions, properties, tasks, tenant_portal, tenants
from app.seed import seed_if_empty

init_db()
with get_connection() as db:
    seed_if_empty(db)

app = FastAPI(title="Apartment Management API", version="0.1.0")

cors_origins = ["http://127.0.0.1:5173", "http://localhost:5173"]
if APP_ENV in {"development", "test"}:
    cors_origins.extend(["http://127.0.0.1:5174", "http://localhost:5174"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(permissions.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(properties.router, prefix="/api")
app.include_router(tenants.router, prefix="/api")
app.include_router(contracts.router, prefix="/api")
app.include_router(maintenance.router, prefix="/api")
app.include_router(finance.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(tenant_portal.router, prefix="/api")


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

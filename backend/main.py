import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_VERSION = ROOT_DIR.joinpath("VERSION").read_text(encoding="utf-8").strip()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.config import (  # noqa: E402
    EXPORTS_DIR,
    GENERATED_ASSETS_DIR,
    REFERENCE_ASSETS_DIR,
    ensure_runtime_dirs,
    is_offline_mode,
)
from backend.app.routes import exports, generation, imports, projects, schedule, settings, shots  # noqa: E402
from backend.app.services.project_service import sanitize_existing_project_logs  # noqa: E402
from backend.app.services.shotlist_service import recover_interrupted_generation_states  # noqa: E402

ensure_runtime_dirs()
sanitize_existing_project_logs()
recover_interrupted_generation_states()

default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
allowed_origins = [
    origin.strip()
    for origin in os.getenv("PANELOOM_ALLOWED_ORIGINS", ",".join(default_origins)).split(",")
    if origin.strip()
]

app = FastAPI(title="Paneloom API", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for route, directory, name in (
    ("/assets/generated", GENERATED_ASSETS_DIR, "generated-assets"),
    ("/assets/references", REFERENCE_ASSETS_DIR, "reference-assets"),
    ("/exports", EXPORTS_DIR, "exports"),
):
    if directory.is_dir():
        app.mount(route, StaticFiles(directory=str(directory)), name=name)


@app.get("/health")
def health() -> dict:
    offline = is_offline_mode()
    return {
        "ok": True,
        "service": "Paneloom API",
        "version": APP_VERSION,
        "offline_mode": offline,
        "cloud_ai_available": not offline,
    }


app.include_router(projects.router)
app.include_router(shots.router)
app.include_router(generation.router)
app.include_router(settings.router)
app.include_router(exports.router)
app.include_router(schedule.router)
app.include_router(imports.router)

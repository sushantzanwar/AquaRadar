"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aquawatch import __version__
from aquawatch.api.deps import build_state
from aquawatch.api.routes import alerts, anomalies, assistant, credits, explain, health, maps, priority, scenes, stress, waterbodies
from aquawatch.settings import load_settings


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="AquaWatch", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.aquawatch = build_state(settings)
    for module in (health, scenes, maps, anomalies, alerts, explain, priority, assistant, credits, stress):
        app.include_router(module.router, prefix="/api")
    app.include_router(waterbodies.router)
    app.include_router(waterbodies.router, prefix="/api")
    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("aquawatch.main:app", host="0.0.0.0", port=8000, reload=False)

"""Application state shared by the routes."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse

from aquawatch.credits.leaderboard import CreditsService
from aquawatch.disclaimer import public_stamp
from aquawatch.llm.assistant import Assistant
from aquawatch.llm.provider import build_provider
from aquawatch.llm.retriever import Retriever
from aquawatch.pipeline.runner import PipelineRunner
from aquawatch.settings import Settings
from aquawatch.storage.baselines import BaselineStore
from aquawatch.storage.products import ProductStore


@dataclass
class AppState:
    settings: Settings
    runner: PipelineRunner
    credits: CreditsService
    assistant: Assistant


def build_state(settings: Settings) -> AppState:
    baselines = BaselineStore(settings.baselines_path, settings.residuals_path)
    products = ProductStore(settings.cache_dir)
    runner = PipelineRunner(settings, baselines, products)
    credits = CreditsService(settings)
    runner.bump_for = credits.bump_for
    provider = build_provider(settings)
    runner.provider = provider
    retriever = Retriever(settings.corpus_dir, settings.cache_dir)
    assistant = Assistant(retriever, provider, settings.disclaimer)
    return AppState(settings=settings, runner=runner, credits=credits, assistant=assistant)


def get_state(request: Request) -> AppState:
    return request.app.state.aquawatch


def error_response(settings: Settings, status_code: int, status: str, reason: str) -> JSONResponse:
    payload = {
        "status": status,
        "reason": reason,
        **public_stamp(0.0, [reason], settings.disclaimer),
    }
    return JSONResponse(status_code=status_code, content=payload)

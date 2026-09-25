"""Science questions answered from the corpus and the monitored water body."""

from fastapi import APIRouter, Depends

from aquawatch.api.deps import AppState, get_state
from aquawatch.api.routes.series_alerts import alerts_for_settings
from aquawatch.domain.schemas import AssistantAnswer, AssistantRequest
from aquawatch.llm.platform import render_platform
from aquawatch.pipeline.temporal import adaptive_series
from aquawatch.storage.zone_series import load_zone_observations

router = APIRouter()


@router.post("/assistant", response_model=AssistantAnswer)
def assistant(body: AssistantRequest, state: AppState = Depends(get_state)) -> AssistantAnswer:
    water_body = state.settings.body(body.water_body_id) if body.water_body_id else None
    evidence = None
    platform = None
    if water_body is not None:
        if body.zone_id and body.date:
            evidence = state.runner.evidence(water_body.id, body.zone_id, body.date)
        scene_status = None
        scene_reason = None
        if body.date:
            analysis = state.runner.analyze(water_body.id, body.date)
            scene_status = analysis.status
            scene_reason = analysis.reason
        observations = load_zone_observations(
            state.settings.products_store,
            water_body.id,
            state.settings.pixel_area_m2,
        )
        platform = render_platform(
            water_body_id=water_body.id,
            water_body_name=water_body.name,
            date=body.date,
            zone_id=body.zone_id,
            scene_status=scene_status,
            scene_reason=scene_reason,
            series=adaptive_series(observations),
            alerts=alerts_for_settings(state, water_body.id),
            evidence=evidence,
            sigma_threshold=state.settings.sigma_threshold,
        )
    return state.assistant.answer(body.question, evidence, platform)

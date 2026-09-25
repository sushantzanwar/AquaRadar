"""Science questions and narration of an evidence card."""

from fastapi import APIRouter, Depends

from aquawatch.api.deps import AppState, get_state
from aquawatch.domain.schemas import AssistantAnswer, AssistantRequest

router = APIRouter()


@router.post("/assistant", response_model=AssistantAnswer)
def assistant(body: AssistantRequest, state: AppState = Depends(get_state)) -> AssistantAnswer:
    evidence = None
    if body.water_body_id and body.zone_id and body.date and state.settings.body(body.water_body_id):
        evidence = state.runner.evidence(body.water_body_id, body.zone_id, body.date)
    return state.assistant.answer(body.question, evidence)

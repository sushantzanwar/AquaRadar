"""The assistant quotes stored series and alerts, and does not call Gemini."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from aquawatch.llm.assistant import Assistant
from aquawatch.llm.platform import render_platform
from aquawatch.llm.provider import build_provider
from aquawatch.llm.retriever import Retriever
from aquawatch.main import create_app
from aquawatch.pipeline.temporal import adaptive_series
from aquawatch.settings import load_settings


def test_platform_text_quotes_the_stored_index_and_alerts(tmp_path):
    rows = [
        {"zone_id": "r0c0", "indicator": "turbidity", "date": "20240115", "value": 1.0, "raster_path": None},
        {"zone_id": "r0c0", "indicator": "turbidity", "date": "20240312", "value": 1.1, "raster_path": None},
        {"zone_id": "r0c0", "indicator": "turbidity", "date": "20241202", "value": 9.0, "raster_path": None},
    ]
    alert = SimpleNamespace(
        severity="high",
        zone_id="r0c0",
        datetime="2024-12-02T00:00:00Z",
        indicators=["turbidity"],
        template="High relative turbidity signal.",
    )
    text = render_platform(
        water_body_id="demo-reservoir",
        water_body_name="Demo Reservoir",
        date="20241202",
        zone_id="r0c0",
        scene_status="missing",
        scene_reason="scene_folder_missing",
        series=adaptive_series(rows),
        alerts=[alert],
        evidence=None,
        sigma_threshold=3,
    )
    assert "Demo Reservoir" in text
    assert "turbidity in r0c0: value 9 " in text
    assert "index" in text
    assert "crossed true" in text
    assert "High relative turbidity signal." in text
    assert "NTU" not in text


def test_gemini_provider_stays_on_the_local_template(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "should-not-be-sent")
    provider = build_provider(load_settings())
    assert provider.name == "none"
    assert provider.complete("turbidity") == ""


def test_rejected_draft_falls_back_to_platform_numbers(tmp_path):
    class Drafts:
        name = "local"

        def complete(self, prompt: str) -> str:
            return "Turbidity is 999 NTU."

    assistant = Assistant(Retriever(tmp_path, tmp_path), Drafts(), "Satellite-derived estimate.")
    platform = "Demo Reservoir turbidity value 1.5 index."
    answer = assistant.answer("What is turbidity?", None, platform)
    assert answer.grounded is True
    assert "999" not in answer.answer
    assert "1.5" in answer.answer
    assert "llm_rejected" in answer.confidence_reasons


def test_api_answer_uses_the_selected_water_body():
    client = TestClient(create_app())
    response = client.post(
        "/api/assistant",
        json={"question": "What are we monitoring here?", "water_body_id": "demo-reservoir", "date": "20241202"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "Demo Reservoir" in payload["answer"]
    assert "turbidity (index)" in payload["answer"]
    assert "No stored zone series" in payload["answer"]
    assert "scene status missing" in payload["answer"]
    assert payload["lab_verification_required"] is True
    assert "gemini" not in payload["answer"].lower()

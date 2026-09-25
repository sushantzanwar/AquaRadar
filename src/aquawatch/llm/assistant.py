"""RAG chatbot assistant — retrieves from corpus, grounds on pipeline evidence, calls LLM."""

from __future__ import annotations

from aquawatch.disclaimer import public_stamp
from aquawatch.domain.schemas import AssistantAnswer, EvidenceCard, Passage
from aquawatch.llm.prompts import build_prompt
from aquawatch.llm.provider import TemplateProvider
from aquawatch.llm.retriever import Retriever
from aquawatch.pipeline.alerts import narrative_respects_evidence


class Assistant:
    def __init__(self, retriever: Retriever, provider, disclaimer: str):
        self.retriever = retriever
        self.provider = provider or TemplateProvider()
        self.disclaimer = disclaimer

    def answer(
        self,
        question: str,
        evidence: EvidenceCard | None = None,
        history: list[dict] | None = None,
    ) -> AssistantAnswer:
        # 1. Retrieve relevant corpus passages (semantic or keyword search)
        search_query = question or _narrate_query(evidence)
        passages = self.retriever.search(search_query)

        evidence_json = evidence.model_dump_json() if evidence else None
        grounded = bool(passages) or evidence is not None
        source = "template"

        if not passages and evidence is None:
            # Nothing to ground on — honest fallback
            text = (
                "I don't have that in my knowledge base. "
                "I can help with: water quality indicators (turbidity, chlorophyll, transparency), "
                "AquaWatch alerts and anomaly scores, WHO/EPA water quality guidelines, "
                "and the current water body data shown on your dashboard."
            )
            source = "template"

        elif self.provider.name == "none":
            # LLM disabled — extractive answer from corpus
            text = _extractive(passages, evidence)
            source = "llm_disabled"

        else:
            # LLM available — build full RAG prompt and generate
            prompt = build_prompt(question, passages, evidence_json, history)
            try:
                drafted = self.provider.complete(prompt, history).strip()
                source = "llm"
            except Exception:
                drafted = ""
                source = "llm_unreachable"

            # Safety check: if evidence provided, ensure LLM answer respects it
            if evidence is not None and drafted and not narrative_respects_evidence(drafted, evidence):
                drafted = ""
                source = "llm_rejected"

            # Fall back to extractive if LLM fails or is rejected
            text = drafted or _extractive(passages, evidence)

        # Build confidence + reasons
        reasons: list[str] = []
        if passages:
            reasons.append("corpus")
        if evidence is not None:
            reasons.append("pipeline_evidence")
        if source != "llm":
            reasons.append(source)
        if not grounded:
            reasons.append("not_in_corpus")

        confidence = evidence.confidence if evidence is not None else (0.75 if passages else 0.2)
        stamp = public_stamp(confidence, reasons, self.disclaimer)

        return AssistantAnswer(
            answer=text,
            source_ids=[p["source_id"] for p in passages],
            passages=[Passage(**p) for p in passages],
            evidence_id=None if evidence is None else evidence.evidence_id,
            grounded=grounded and source not in {"template", "not_in_corpus"},
            **stamp,
        )


def _narrate_query(evidence: EvidenceCard | None) -> str:
    """Generate a retrieval query from evidence when no explicit question is asked."""
    if evidence is None:
        return "water quality indicator baseline confidence disclaimer"
    names = " ".join(evidence.contributing_indicators) or "indicator baseline anomaly"
    return f"alert explanation {names} sigma threshold why flagged interpretation"


def _extractive(passages: list[dict], evidence: EvidenceCard | None) -> str:
    """Fallback: extract relevant text from corpus passages + evidence numbers."""
    lines: list[str] = []

    if passages:
        lines.append("📚 **From the knowledge base:**")
        for passage in passages:
            lines.append(f"\n**[{passage['source_id']}] {passage['title']}**\n{passage['text']}")

    if evidence is not None:
        lines.append("\n📊 **Current pipeline evidence:**")
        for row in evidence.comparisons:
            sigma = "n/a" if row.sigma is None else f"{row.sigma:.2f}σ"
            crossed = "⚠️ threshold crossed" if row.crossed else "within normal range"
            lines.append(
                f"• **{row.indicator}**: value {row.value:.4g}, "
                f"baseline {row.baseline_mean:.4g} ± {row.baseline_std}, "
                f"deviation {sigma} — {crossed}"
            )
        if evidence.contributing_indicators:
            lines.append(f"• **Flagged indicators**: {', '.join(evidence.contributing_indicators)}")

    if not lines:
        return (
            "I don't have that in my knowledge base. "
            "I can help with water quality indicators, AquaWatch alerts, WHO/EPA guidelines, "
            "and the current water body data shown on the dashboard."
        )

    lines.append(
        "\n⚠️ *Note: Language model is not configured. "
        "Set LLM_PROVIDER=gemini and LLM_API_KEY in your environment to enable AI-generated answers.*"
    )
    return "\n".join(lines)

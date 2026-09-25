"""One assistant for science questions and for narrating pipeline evidence."""

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

    def answer(self, question: str, evidence: EvidenceCard | None = None) -> AssistantAnswer:
        passages = self.retriever.search(question or _narrate_query(evidence))
        evidence_json = evidence.model_dump_json() if evidence else None
        grounded = bool(passages) or evidence is not None
        if not passages and evidence is None:
            text = "Not in corpus. I can only answer from the AquaWatch documents and pipeline evidence."
            source = "template"
        elif self.provider.name == "none":
            text = _extractive(passages, evidence)
            source = "llm_disabled"
        else:
            prompt = build_prompt(question, passages, evidence_json)
            try:
                drafted = self.provider.complete(prompt).strip()
            except Exception:
                drafted = ""
                source = "llm_unreachable"
            else:
                source = "llm"
            if evidence is not None and drafted and not narrative_respects_evidence(drafted, evidence):
                drafted = ""
                source = "llm_rejected"
            text = drafted or _extractive(passages, evidence)
        reasons = ["corpus"] if passages else []
        if evidence is not None:
            reasons.append("pipeline_evidence")
        if source != "llm":
            reasons.append(source)
        if not grounded:
            reasons.append("not_in_corpus")
        confidence = evidence.confidence if evidence is not None else (0.7 if passages else 0.2)
        stamp = public_stamp(confidence, reasons, self.disclaimer)
        return AssistantAnswer(
            answer=text,
            source_ids=[passage["source_id"] for passage in passages],
            passages=[Passage(**passage) for passage in passages],
            evidence_id=None if evidence is None else evidence.evidence_id,
            grounded=grounded and source != "not_in_corpus",
            **stamp,
        )


def _narrate_query(evidence: EvidenceCard | None) -> str:
    if evidence is None:
        return "product boundary confidence disclaimer"
    names = " ".join(evidence.contributing_indicators) or "indicator baseline"
    return f"alert language {names} why flagged sigma baseline"


def _extractive(passages: list[dict], evidence: EvidenceCard | None) -> str:
    lines = ["Language model disabled. Showing retrieved corpus text and pipeline numbers only."]
    for passage in passages:
        lines.append(f"[{passage['source_id']}] {passage['text']}")
    if evidence is not None:
        lines.append("Pipeline evidence:")
        for row in evidence.comparisons:
            sigma = "n/a" if row.sigma is None else f"{row.sigma:.2f}"
            lines.append(
                f"{row.indicator}: value {row.value:.4g}, baseline mean {row.baseline_mean:.4g}, "
                f"std {row.baseline_std}, sigma {sigma}, crossed {row.crossed}."
            )
        lines.append(f"Contributing indicators: {', '.join(evidence.contributing_indicators) or 'none'}.")
    if not passages and evidence is None:
        return "Not in corpus."
    return "\n\n".join(lines)

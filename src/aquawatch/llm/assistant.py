"""One assistant for science questions and for narrating pipeline evidence."""

from __future__ import annotations

from aquawatch.disclaimer import public_stamp
from aquawatch.domain.schemas import AssistantAnswer, EvidenceCard, Passage
from aquawatch.llm.prompts import build_prompt
from aquawatch.llm.provider import TemplateProvider
from aquawatch.llm.retriever import Retriever
from aquawatch.pipeline.alerts import allowed_numbers, math_close, numbers_in_text


class Assistant:
    def __init__(self, retriever: Retriever, provider, disclaimer: str):
        self.retriever = retriever
        self.provider = provider or TemplateProvider()
        self.disclaimer = disclaimer

    def answer(
        self,
        question: str,
        evidence: EvidenceCard | None = None,
        platform: str | None = None,
    ) -> AssistantAnswer:
        passages = self.retriever.search(question or _narrate_query(evidence, platform))
        evidence_json = evidence.model_dump_json() if evidence else None
        grounded = bool(passages) or evidence is not None or bool(platform)
        if not grounded:
            text = "Not in corpus. Select a monitored water body to use its indicator series and alerts."
            source = "template"
        elif self.provider.name == "none":
            text = _compose(passages, evidence, platform)
            source = "llm_disabled"
        else:
            prompt = build_prompt(question, passages, evidence_json, platform)
            try:
                drafted = self.provider.complete(prompt).strip()
            except Exception:
                drafted = ""
                source = "llm_unreachable"
            else:
                source = "llm"
            if drafted and not _respects(drafted, evidence, platform, passages):
                drafted = ""
                source = "llm_rejected"
            text = drafted or _compose(passages, evidence, platform)
        reasons = ["corpus"] if passages else []
        if platform:
            reasons.append("platform_series")
        if evidence is not None:
            reasons.append("pipeline_evidence")
        if source != "llm":
            reasons.append(source)
        if not grounded:
            reasons.append("not_in_corpus")
        confidence = evidence.confidence if evidence is not None else (0.7 if platform or passages else 0.2)
        stamp = public_stamp(confidence, reasons, self.disclaimer)
        return AssistantAnswer(
            answer=text,
            source_ids=[passage["source_id"] for passage in passages],
            passages=[Passage(**passage) for passage in passages],
            evidence_id=None if evidence is None else evidence.evidence_id,
            grounded=grounded and source != "not_in_corpus",
            **stamp,
        )


def _narrate_query(evidence: EvidenceCard | None, platform: str | None) -> str:
    if evidence is None and not platform:
        return "product boundary confidence disclaimer"
    names = " ".join(evidence.contributing_indicators) if evidence else "turbidity chlorophyll transparency extent"
    return f"relative index {names} sigma baseline laboratory verification"


def _compose(passages: list[dict], evidence: EvidenceCard | None, platform: str | None) -> str:
    blocks: list[str] = []
    if platform:
        blocks.append(platform)
    elif evidence is not None:
        blocks.append(_evidence_block(evidence))
    if passages:
        blocks.append("Notes from the AquaWatch corpus:")
        for passage in passages[:2]:
            text = passage["text"].strip()
            if len(text) > 700:
                text = text[:700].rstrip() + "…"
            blocks.append(f"[{passage['source_id']}] {passage['title']}\n{text}")
    if not blocks:
        return "Not in corpus. Select a monitored water body to use its indicator series and alerts."
    return "\n\n".join(blocks)


def _evidence_block(evidence: EvidenceCard) -> str:
    lines = [f"Scene evidence for {evidence.zone_name} on {evidence.date}:"]
    for row in evidence.comparisons:
        sigma = "n/a" if row.sigma is None else f"{row.sigma:.2f}"
        lines.append(
            f"- {row.indicator}: value {row.value:.4g}, baseline mean {row.baseline_mean:.4g}, "
            f"std {row.baseline_std}, sigma {sigma}, crossed {str(row.crossed).lower()}."
        )
    lines.append(f"Contributing indicators: {', '.join(evidence.contributing_indicators) or 'none'}.")
    return "\n".join(lines)


def _respects(text: str, evidence: EvidenceCard | None, platform: str | None, passages: list[dict]) -> bool:
    extra = numbers_in_text(platform or "")
    for passage in passages:
        extra.extend(numbers_in_text(passage["text"]))
    if evidence is None:
        if not extra:
            return not numbers_in_text(text)
        return all(any(math_close(number, candidate) for candidate in extra) for number in numbers_in_text(text))
    allowed = allowed_numbers(evidence, extra)
    return all(any(math_close(number, candidate) for candidate in allowed) for number in numbers_in_text(text))

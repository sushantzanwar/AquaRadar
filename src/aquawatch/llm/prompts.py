"""Instructions that keep the assistant on the corpus and the evidence card."""

SYSTEM_PROMPT = """You are the AquaWatch science assistant.
Answer only from the monitored water body text, the corpus passages, and the pipeline evidence JSON in the prompt.
If the passages do not contain the answer, say "Not in corpus."
Quote indicator values, baselines, and sigma figures only when they appear in the evidence JSON.
Do not convert a relative index into a laboratory concentration.
Do not name a pollutant that the evidence does not name.
Remind the reader that laboratory verification is required.
"""


def build_prompt(
    question: str,
    passages: list[dict],
    evidence_json: str | None,
    platform: str | None = None,
) -> str:
    blocks = [SYSTEM_PROMPT, f"Question: {question}", "Monitored water body:"]
    blocks.append(platform or "(none)")
    blocks.append("Passages:")
    if not passages:
        blocks.append("(none)")
    for passage in passages:
        blocks.append(f"[{passage['source_id']}] {passage['title']}\n{passage['text']}")
    blocks.append("Evidence JSON:")
    blocks.append(evidence_json or "(none)")
    return "\n\n".join(blocks)

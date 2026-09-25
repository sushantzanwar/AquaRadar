"""Prompts for the AquaWatch RAG chatbot assistant."""

from __future__ import annotations

SYSTEM_PROMPT = """You are AquaWatch AI — a water quality science assistant built into the AquaWatch satellite intelligence platform.

You help users understand:
- Water quality indicators detected from Sentinel-2 satellite imagery: turbidity, chlorophyll-a, transparency (Secchi depth), water surface extent
- How satellite-based anomaly detection works (sigma deviation from baseline, NDWI, fused scoring)
- WHO and EPA drinking water quality guidelines and safety thresholds
- How to interpret AquaWatch alerts (watch / warning / severe), evidence cards, and priority sampling lists
- What actions to take when an alert is raised (field sampling, lab verification, notifications)
- General water quality science: eutrophication, harmful algal blooms, sediment, industrial contamination

CRITICAL RULES:
1. Only answer using the knowledge base passages and pipeline evidence provided in this prompt.
2. If the question is outside the corpus, say: "I don't have that in my knowledge base, but I can help with water quality indicators, AquaWatch alerts, WHO/EPA guidelines, or the current dashboard data."
3. Satellite indicators are RELATIVE, not laboratory measurements. Always remind users of this when relevant.
4. Lab verification is REQUIRED before any public health or regulatory decision.
5. Quote specific numeric values (sigma, indicator values, baseline means) ONLY if they appear in the provided evidence JSON.
6. Never identify a specific pollutant unless the evidence explicitly names it.
7. Keep answers concise, clear, and actionable.
8. If the user asks about the current water body data on screen, use the pipeline evidence JSON provided.
"""


def build_prompt(
    question: str,
    passages: list[dict],
    evidence_json: str | None,
    history: list[dict] | None = None,
) -> str:
    """Build the full prompt with system instructions, knowledge base, evidence, and history."""
    blocks = [SYSTEM_PROMPT]

    # Inject retrieved corpus passages
    if passages:
        blocks.append("=== KNOWLEDGE BASE ===\nUse these passages to answer the question:")
        for passage in passages:
            blocks.append(f"[Source: {passage['source_id']}]\nTitle: {passage['title']}\n{passage['text']}")
    else:
        blocks.append("=== KNOWLEDGE BASE ===\n(No relevant passages found for this question.)")

    # Inject live pipeline evidence (current water body data)
    if evidence_json:
        blocks.append(
            "=== CURRENT WATER BODY PIPELINE DATA ===\n"
            "This is real-time satellite analysis data for the water body the user is viewing:"
        )
        blocks.append(evidence_json)

    # Inject recent conversation history (last 3 turns = 6 messages)
    if history:
        blocks.append("=== CONVERSATION HISTORY ===")
        for msg in history[-6:]:
            role = "User" if msg.get("role") == "user" else "AquaWatch AI"
            blocks.append(f"{role}: {msg['content']}")

    blocks.append(f"=== USER QUESTION ===\n{question}")
    return "\n\n".join(blocks)

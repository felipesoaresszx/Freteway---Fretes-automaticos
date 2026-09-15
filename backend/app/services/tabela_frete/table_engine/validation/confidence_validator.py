from __future__ import annotations


def evaluate_confidence(score: float) -> dict[str, object]:
    return {
        "score": max(0.0, min(1.0, score)),
        "status": "high" if score >= 0.8 else "medium" if score >= 0.5 else "low",
    }

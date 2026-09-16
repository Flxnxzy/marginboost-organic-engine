from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict


ZA_TERMS = {
    "south africa": 5,
    "south african": 5,
    "johannesburg": 4,
    "joburg": 4,
    "cape town": 4,
    "durban": 4,
    "pretoria": 4,
    "gauteng": 4,
    "western cape": 4,
    "kwazulu-natal": 4,
    "kzn": 4,
    "zar": 3,
    "rand": 3,
}

BPO_TERMS = {
    "bpo": 5,
    "business process outsourcing": 6,
    "outsourcing": 4,
    "outsource": 4,
    "outsourced": 4,
    "subcontract": 4,
    "subcontracting": 4,
    "white label": 4,
    "white-label": 4,
    "virtual assistant": 3,
    "va agency": 4,
    "upwork": 4,
    "fiverr": 4,
    "freelancer": 3,
    "freelance": 3,
    "remote client": 3,
    "client work": 2,
    "agency": 2,
}

INTENT_TERMS = {
    "looking for": 3,
    "need help": 3,
    "need a": 2,
    "how do i": 2,
    "how to": 2,
    "client": 2,
    "proposal": 2,
    "quote": 2,
    "margin": 4,
    "profit": 3,
    "pricing": 3,
    "manage": 2,
    "management": 2,
    "scale": 3,
    "scaling": 3,
    "software": 3,
    "tool": 2,
    "crm": 3,
    "job": 1,
    "project": 1,
    "hiring": 2,
    "hire": 2,
}


@dataclass
class ScoredItem:
    item: dict
    score: int
    matches: list[str]

    def to_dict(self):
        return {
            **self.item,
            "score": self.score,
            "matches": self.matches,
        }


def _score_terms(text: str, terms: dict[str, int]):
    score = 0
    hits = []
    for term, weight in terms.items():
        if term in text:
            score += weight
            hits.append(term)
    return score, hits


def score_item(item: dict) -> ScoredItem:
    text = f"{item.get('title','')} {item.get('summary','')}".lower()

    za_score, za_hits = _score_terms(text, ZA_TERMS)
    bpo_score, bpo_hits = _score_terms(text, BPO_TERMS)
    intent_score, intent_hits = _score_terms(text, INTENT_TERMS)

    extra_keywords = [x.strip().lower() for x in os.getenv("EXTRA_KEYWORDS", "").split(",") if x.strip()]
    extra_hits = [k for k in extra_keywords if k in text]

    score = za_score + bpo_score + intent_score + (2 * len(extra_hits))

    # Require meaningful South-African and BPO relevance before a topic is considered strong.
    if not za_hits:
        score -= 5
    if not bpo_hits:
        score -= 5

    return ScoredItem(
        item=item,
        score=max(score, 0),
        matches=sorted(set(za_hits + bpo_hits + intent_hits + extra_hits)),
    )

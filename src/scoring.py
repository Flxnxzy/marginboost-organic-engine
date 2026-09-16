from __future__ import annotations

import os
from dataclasses import dataclass


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
    "rand": 2,
}

STRONG_BPO_TERMS = {
    "bpo": 6,
    "business process outsourcing": 7,
    "outsourcing": 5,
    "outsource": 5,
    "outsourced": 5,
    "subcontract": 5,
    "subcontracting": 5,
    "white label": 5,
    "white-label": 5,
    "virtual assistant agency": 5,
    "va agency": 5,
    "outsourcing agency": 6,
}

FREELANCE_TERMS = {
    "upwork": 4,
    "fiverr": 4,
    "freelancer": 3,
    "freelance": 3,
}

OPERATOR_TERMS = {
    "client": 3,
    "clients": 3,
    "agency": 3,
    "team": 2,
    "contractor": 2,
    "delivery": 3,
    "fulfilment": 3,
    "fulfillment": 3,
    "hire": 2,
    "hiring": 2,
    "proposal": 2,
    "margin": 5,
    "profit": 4,
    "pricing": 3,
    "scale": 3,
    "scaling": 3,
    "crm": 3,
}

INTENT_TERMS = {
    "looking for": 2,
    "need help": 3,
    "how do i": 3,
    "how to": 2,
    "software": 3,
    "tool": 2,
    "manage": 2,
    "management": 2,
}

NEGATIVE_TERMS = {
    "invest in south africa",
    "moving to south africa",
    "move to south africa",
    "tourist",
    "tourism",
    "travel itinerary",
    "visa advice",
}


@dataclass
class ScoredItem:
    item: dict
    score: int
    matches: list[str]

    def to_dict(self):
        return {**self.item, "score": self.score, "matches": self.matches}


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
    strong_score, strong_hits = _score_terms(text, STRONG_BPO_TERMS)
    freelance_score, freelance_hits = _score_terms(text, FREELANCE_TERMS)
    operator_score, operator_hits = _score_terms(text, OPERATOR_TERMS)
    intent_score, intent_hits = _score_terms(text, INTENT_TERMS)

    extra_keywords = [x.strip().lower() for x in os.getenv("EXTRA_KEYWORDS", "").split(",") if x.strip()]
    extra_hits = [k for k in extra_keywords if k in text]

    # Hard gates: must be South African, and must look like someone actually
    # operating outsourced/freelance client delivery rather than generic SA chatter.
    relevant_operator = bool(strong_hits) or (bool(freelance_hits) and bool(operator_hits))
    negative = any(term in text for term in NEGATIVE_TERMS)

    if not za_hits or not relevant_operator or negative:
        return ScoredItem(item=item, score=0, matches=[])

    score = (
        za_score
        + strong_score
        + freelance_score
        + operator_score
        + intent_score
        + (2 * len(extra_hits))
    )

    return ScoredItem(
        item=item,
        score=score,
        matches=sorted(set(
            za_hits + strong_hits + freelance_hits + operator_hits + intent_hits + extra_hits
        )),
    )
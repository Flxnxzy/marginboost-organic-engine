from __future__ import annotations

from .util import tracked_url


def build_reply(candidate: dict, marginboost_url: str) -> str:
    text = candidate.get("text", "").lower()
    short_id = candidate.get("id", "reply")[:10]
    link = tracked_url(
        marginboost_url,
        source="bluesky",
        medium="organic-reply",
        campaign="high-intent-conversations",
        content=short_id,
    )

    if "margin" in text or "profit" in text or "pricing" in text:
        helpful = (
            "For outsourced delivery, Iâ€™d track client revenue minus fulfilment cost per job first; "
            "that usually exposes where margin is leaking."
        )
    elif "upwork" in text or "fiverr" in text or "freelanc" in text:
        helpful = (
            "If youâ€™re winning client work and subcontracting delivery, the hard part becomes keeping "
            "client value, fulfilment cost, deadlines and margin tied to the same job."
        )
    elif "subcontract" in text or "outsourc" in text or "bpo" in text:
        helpful = (
            "Once delivery is outsourced, a simple per-job view of client revenue, delivery cost, owner "
            "and deadline prevents a lot of margin and handoff problems."
        )
    else:
        helpful = (
            "The cleanest setup is to keep the client, delivery owner, fulfilment cost and margin attached "
            "to each job instead of splitting them across chats and spreadsheets."
        )

    cta = f"MarginBoost is built around that workflow for South African BPO operators: {link}"
    reply = f"{helpful}\n\n{cta}"

    # Bluesky posts are limited; preserve the full tracked link.
    if len(reply) > 300:
        reply = f"Track client revenue, fulfilment cost, delivery owner and margin per job. MarginBoost is built for that workflow in SA BPO: {link}"

    return reply
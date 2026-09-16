from __future__ import annotations

from .util import tracked_url, normalize_space


TEMPLATES = [
    "Running outsourced client work? Track client revenue, fulfilment cost and margin before you scale. {cta}",
    "Winning the client is only half the BPO job. Know what the client pays, what delivery costs and what margin remains. {cta}",
    "Using freelancers or subcontractors to deliver client work? Keep clients, delivery costs and margin visible in one place. {cta}",
    "More outsourced work does not automatically mean more profit. Track each job's revenue, delivery cost and margin. {cta}",
]


def build_post(item: dict, index: int, marginboost_url: str) -> str:
    title = normalize_space(item.get("title", ""))
    link = tracked_url(marginboost_url, "bluesky")
    cta = f"Built for South African BPO operators: {link}"

    body = TEMPLATES[index % len(TEMPLATES)].format(cta=cta)

    if title:
        context = title[:70].rstrip(" -|:")
        candidate = f"On the radar: {context}\n\n{body}"
        if len(candidate) <= 300:
            body = candidate

    # Never truncate the CTA or tracked link.
    if len(body) > 300:
        body = f"Running outsourced client work? Track revenue, delivery cost and margin in one place. {cta}"

    return body
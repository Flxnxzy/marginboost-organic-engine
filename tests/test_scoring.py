from src.scoring import score_item
from src.content import build_post
from src.bluesky_discovery import score_candidate, score_relevance
from src.engagement import build_reply


def test_strong_sa_bpo_item():
    item = {
        "title": "South African Upwork freelancer scaling an outsourcing agency",
        "summary": "How do I manage client margin and subcontractors in Johannesburg?",
        "url": "https://example.com/1",
        "source": "test",
        "id": "x",
        "published": None,
    }
    assert score_item(item).score >= 8


def test_weak_unrelated_item():
    item = {
        "title": "Weather update",
        "summary": "Sunny today",
        "url": "https://example.com/2",
        "source": "test",
        "id": "y",
        "published": None,
    }
    assert score_item(item).score == 0


def test_investment_chatter_is_rejected():
    item = {
        "title": "I want to live and invest in SA",
        "summary": "South Africa Johannesburg Cape Town freelance jobs and general advice",
        "url": "https://example.com/3",
        "source": "test",
        "id": "z",
        "published": None,
    }
    assert score_item(item).score == 0


def test_post_never_truncates_cta_link():
    item = {
        "title": "A very long topic title " * 20,
        "source": "test",
    }
    post = build_post(item, 0, "https://marginboost.co.za")
    assert len(post) <= 300
    assert "https://marginboost.co.za" in post


def test_high_intent_bluesky_candidate():
    score, matches = score_candidate(
        "South African Upwork agency here. We outsource client delivery and I am struggling "
        "to track subcontractor costs and profit. What tool do you use?"
    )
    assert score >= 20
    assert "upwork" in matches


def test_job_seeker_not_targeted():
    score, _ = score_candidate(
        "South African freelancer looking for a job on Upwork. Anyone hiring?"
    )
    assert score == 0


def test_generic_sa_chat_not_targeted():
    score, _ = score_candidate(
        "South Africa is beautiful. Any advice for Cape Town?"
    )
    assert score == 0


def test_reply_contains_full_tracked_link():
    candidate = {
        "id": "abcdefghij123",
        "text": "South African Upwork agency outsourcing client work and struggling with margin",
    }
    reply = build_reply(candidate, "https://marginboost.co.za")
    assert len(reply) <= 300
    assert "https://marginboost.co.za" in reply
    assert "utm_medium=organic-reply" in reply
    assert "utm_content=abcdefghij" in reply

def test_construction_subcontractor_is_rejected():
    score, _ = score_candidate(
        "The construction and engineering sector in South Africa must manage multiple "
        "project sites, subcontractor ecosystems and safety compliance requirements."
    )
    assert score == 0


def test_real_sa_outsourcing_operator_is_kept():
    score, _ = score_candidate(
        "South African Upwork freelancer here. I outsource client delivery to contractors "
        "and need help tracking margin and managing the workflow. What tool do you use?"
    )
    assert score >= 18

def test_relevance_can_like_without_sales_reply():
    text = (
        "South African Upwork freelancer sharing how I organise client delivery "
        "and my freelance agency workflow."
    )
    relevance, matches = score_relevance(text)
    reply_score, _ = score_candidate(text)
    assert relevance >= 12
    assert "upwork" in matches
    assert reply_score == 0


def test_construction_is_not_even_like_relevant():
    relevance, _ = score_relevance(
        "South Africa construction engineering project sites and subcontractor management"
    )
    assert relevance == 0

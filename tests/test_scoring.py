from src.scoring import score_item
from src.content import build_post


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
    assert "utm_source=bluesky" in post
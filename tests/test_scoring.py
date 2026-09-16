from src.scoring import score_item


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

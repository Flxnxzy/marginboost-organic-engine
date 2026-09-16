from src.reddit_discovery import score_intent, score_relevance
from src.reddit_engagement import subreddit_allows_promo, build_comment

def test_reddit_sa_upwork_operator_is_relevant():
    rel, matches = score_relevance(
        "Scaling my Upwork work in South Africa",
        "I have multiple clients and an agency workflow.",
    )
    assert rel > 0
    assert "upwork" in matches

def test_reddit_high_intent_operator_qualifies():
    score, matches = score_intent(
        "How do I track my outsourcing margin?",
        "South African Upwork freelancer. I outsource client delivery and need help tracking profit.",
    )
    assert score >= 18
    assert "margin" in matches

def test_reddit_job_seeker_is_rejected():
    rel, _ = score_relevance(
        "Need a job",
        "South African freelancer looking for a job on Upwork.",
    )
    assert rel == 0

def test_reddit_construction_false_positive_rejected():
    rel, _ = score_relevance(
        "South Africa outsourcing",
        "Construction engineering subcontractor project sites.",
    )
    assert rel == 0

def test_subreddit_no_promo_rule_blocks_commenting():
    payload = {"rules": [{"short_name": "No self-promotion", "description": "No advertising or promotional links."}]}
    assert not subreddit_allows_promo(payload)

def test_subreddit_without_promo_rule_passes_rule_scan():
    payload = {"rules": [{"short_name": "Be civil", "description": "No personal attacks."}]}
    assert subreddit_allows_promo(payload)

def test_reddit_comment_discloses_affiliation_and_tracks():
    comment = build_comment(
        {
            "id": "abcdef123456",
            "title": "How do I track margin",
            "body": "South Africa Upwork outsourcing client work",
        },
        "https://marginboost.co.za",
    )
    assert "Disclosure: I run MarginBoost" in comment
    assert "utm_source=reddit" in comment
    assert "utm_medium=organic-comment" in comment

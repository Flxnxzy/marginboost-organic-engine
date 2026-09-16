# MarginBoost Organic Engine

Automated, zero-ad-spend organic acquisition engine for MarginBoost.

This repo is designed to run on GitHub Actions, not on the MarginBoost production server.

## What it does

- Monitors public RSS/search feeds for South African BPO, outsourcing and freelance topics.
- Scores each item for South African relevance, BPO/outsourcing relevance and buying/operational intent.
- Creates short, useful organic posts with tracked MarginBoost links.
- Publishes automatically to configured Bluesky and/or Mastodon accounts using official APIs.
- Keeps hard daily posting limits and deduplicates topics.
- Stores a compact state file in the repo so the workflow learns what it has already processed.
- Never sends unsolicited DMs and never creates accounts.

## Default targeting

The engine prioritises South African people already operating around:

- BPO / business process outsourcing
- Upwork, Fiverr and freelance delivery
- subcontracting and white-label delivery
- virtual-assistant agencies
- remote client work
- outsourced project delivery
- margin/profit management
- scaling an outsourcing operation

## Required setup

The engine can run discovery-only with no credentials.

To auto-publish to Bluesky, add these GitHub Actions secrets:

- `BLUESKY_HANDLE`
- `BLUESKY_APP_PASSWORD`

To auto-publish to Mastodon, add:

- `MASTODON_BASE_URL`
- `MASTODON_ACCESS_TOKEN`

No MarginBoost server credentials are required.

## Workflow

`.github/workflows/organic-engine.yml` runs every 4 hours and can also be started manually from GitHub Actions.

The workflow has `contents: write` permission so it can persist `data/state.json` and `data/latest.json`.

## Environment variables

- `AUTO_PUBLISH=true|false` — default workflow value is `true`; missing publisher credentials simply skip that publisher.
- `MAX_POSTS_PER_RUN` — default `1`.
- `MAX_POSTS_PER_DAY` — default `3`.
- `MIN_SCORE` — default `8`.
- `MARGINBOOST_URL` — default `https://marginboost.co.za`.
- `EXTRA_FEEDS` — optional newline-separated RSS/Atom URLs.
- `EXTRA_KEYWORDS` — optional comma-separated targeting keywords.

## Anti-spam defaults

The engine deliberately does **not**:

- mass-DM people;
- scrape private profiles;
- create fake accounts;
- auto-reply to individuals;
- post more than the configured daily cap;
- copy source text verbatim into promotional posts.

Organic publishing is limited to accounts you explicitly authenticate.

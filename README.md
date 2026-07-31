# PlayStats

PlayStats is a Steam stats app that fetches a user's Steam library and answers plain-English questions about it. Give it a SteamID64 and ask things like "what are my most played games?" or "what's my best value per hour?"

# Setup
Create a .env file in the project root (gitignored) with:
STEAM_API_KEY=your_steam_web_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

Install dependencies into your virtualenv (no Pipfile yet, so install directly):
pip install requests python-dotenv anthropic

# Usage

There's no Streamlit UI yet, so everything needs to be run directly through the modules.

from analytics import most_played_games, profile_summary
from intent_router import route_intent

most_played_games("your_steamid64")
route_intent("what are my most played games?")

# Architecture

steam_client.py — thin wrapper around the Steam Web API and Store API. Handles auth, JSON caching (cache/), and raises typed errors (InvalidSteamIDError, PrivateProfileError, EmptyProfileError) instead of surfacing raw exceptions.

analytics.py — deterministic computation layer on top of steam_client.py. Implements the six supported analytics views: most_played_games, least_played_games, genre_breakdown, recent_activity, value_per_hour, profile_summary.

intent_router.py — classifies a free-text question into one of the six intents (or "unsupported") using Claude. See AI Usage below.

app.py (Sprint 3, not yet built) — will dispatch a classified intent to its matching analytics function and render the result with Streamlit/Plotly.

# AI usage

In the app (runtime): PlayStats uses the Claude API (claude-haiku-4-5-20251001) in intent_router.py as an intent classifier only. It reads a user's free-text question and returns one of six fixed intents (mostPlayedGames, leastPlayedGames, genreBreakdown, recentActivity, valuePerHour, profileSummary) or "unsupported" — enforced via a strict Pydantic schema so no other value can be returned. Claude never computes statistics, generates numbers, or writes the user-facing answer; all actual analysis is done by the deterministic functions in analytics.py. This split keeps answers reproducible and avoids relying on the model for accuracy.

In development: Claude Code was used as a development aid while building this project — reviewing hand-written code for bugs, answering design questions, and confirming alignment with the project plan. All code in this repository was written by me, Leoniide Tael. Claude was not used to autonomously generate or commit code. Claude was also used to help make sure all the crucial points were covered in the ReadMe.

# Known limitations

Only numeric SteamID64 input is supported — vanity URL resolution is not implemented yet.

Genre data is estimated from Steam Store metadata and may be incomplete or missing for some games.

Pricing reflects current Steam Store listings and may not account for sales, bundles, or regional pricing.

Profiles must be public. Private or invalid profiles return a friendly error rather than raw data.

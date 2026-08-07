# PlayStats

PlayStats is a Steam stats app that fetches a user's Steam library and answers plain-English questions about it. Give it a SteamID64, a Steam vanity name, or a full profile link, and ask things like "what are my most played games?" or "what's my best value per hour?" and receive a graph that summarizes the question as well as a summary created by Claude.

# Setup
Create a .env file in the project root (gitignored) with:
STEAM_API_KEY=your_steam_web_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

Install dependencies into your virtualenv (no Pipfile yet, so install directly):
pip install requests python-dotenv anthropic streamlit plotly pandas

# Usage

PlayStats isn't deployed anywhere. run it locally with:

streamlit run app.py

This opens a local browser tab (usually http://localhost:8501). Enter a public SteamID64, a Steam vanity name (e.g. gabelogannewell), or a full profile link (e.g. https://steamcommunity.com/id/gabelogannewell/). You'll see a profile card (avatar, games owned, total hours, Steam Level, badges) and a top-10 games chart, plus an "Ask PlayStats" box — click one of the six suggested-question chips to auto-fill a question, or type your own, then hit Ask.

You can also use the modules directly in a script instead of the UI:

from analytics import most_played_games, profile_summary
from intent_router import route_intent

most_played_games("your_steamid64")
route_intent("what are my most played games?")

# Architecture

steam_client.py: thin wrapper around the Steam Web API and Store API. Handles auth, JSON caching (cache/), resolves numeric SteamIDs, vanity names, and full profile links to a SteamID64, and raises typed errors (InvalidSteamIDError, PrivateProfileError, EmptyProfileError) instead of surfacing raw exceptions.

analytics.py: deterministic computation layer on top of steam_client.py. Implements the six supported analytics views: most_played_games, least_played_games, genre_breakdown, recent_activity, value_per_hour, profile_summary (person info such as profile picture, library size, total hours, Steam Level, and badge count).

intent_router.py: classifies a free-text question into one of the six intents (or "unsupported") using Claude, and separately asks Claude to write a short plain-language summary of the already-computed result.

app.py: Streamlit UI. Shows a SteamID/vanity-name/profile-link input, a profile card, and a top-10-games chart, plus an "Ask PlayStats" box with six suggested-question chips (one per supported intent) that dispatches the classified question to its matching analytics.py function and renders the result as a Plotly chart with a Claude-written summary above it. Surfaces friendly errors for Steam API failures, Claude failures, and unsupported questions.

.streamlit/config.toml — custom color theme for the app to follow the Steam color palette.

# AI usage

In the app: PlayStats uses the Claude API (claude-haiku-4-5) in two places. intent_router.py's route_intent reads a user's free-text question and returns one of six fixed intents (mostPlayedGames, leastPlayedGames, genreBreakdown, recentActivity, valuePerHour, profileSummary) or "unsupported" which is enforced via a strict Pydantic schema so no other value can be returned. Claude never computes statistics or generates numbers for this step; all analysis is done by the deterministic functions in analytics.py. Separately, once an intent's data has been computed, summarize_result asks Claude to write a 3-5 sentence plain-language summary of that already-computed data (e.g. "your most played game is X with Y hours"). Claude only restates and explains numbers that already exist in the JSON it's given, it never calculates or invents any of its own. This keeps every number in the app traceable to Python, while still giving the user a plain-English explanation of what each chart shows so they don't have to perform the data anlytics themselves.

In development: Claude Code was used as a development aid while building this project. reviewing hand-written code for bugs, answering design questions, and confirming alignment with the project plan to make sure nothing was overlooked. All code in this repository was written by me, Leoniide Tael. Claude was not used to autonomously generate or commit code.

# Known limitations

Genre data is estimated from Steam Store metadata and may be incomplete or missing for some games.

Pricing reflects current Steam Store listings and may not account for sales, bundles, or regional pricing.

Profiles must be public. Private or invalid profiles return a friendly error rather than raw data. Note: a profile can be publicly visible while still having its "Game Details" privacy setting hidden in Steam's own settings, in that case PlayStats will show "no games to display" even though the profile itself loaded, since Steam's API doesn't distinguish that case from a genuinely empty library.

This app is not deployed. It currently only runs locally.
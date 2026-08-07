import os
import json
import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Literal

# Anthropic SDK auto-reads the variable from the enviornment so it doesn't need to be
# passed manually
load_dotenv()
client = anthropic.Anthropic()

# Single named constant so the model can be easily swapped later. I chose Haiku because it's only a 
# 7-way intent classification so a larger model isn't required.
MODEL = "claude-haiku-4-5-20251001"

class IntentRouterError(Exception):
    """
    Base class for every error raised by the model, this includes the Claude API failures.
    It mirrors steam_client.py's Steam APIError so callers can catch broadly and/or specifically.
    """

class IntentClassificationError(IntentRouterError):
    """
    Raised when Claude's reponse couldnt become a valid intent. For example, refusal, truncated output,
    or failed schema validation. Only one subclass exists because "no match" is a successful classification
    and not an error case.
    """

# The siz intents CLAUDE.d fixes as the whole initial scope. It's a list so FALLBACK_MESSAGe and
# any future validation can reference the truth from the same source.
SUPPORTED_INTENTS = [
    "mostPlayedGames", "leastPlayedGames", "genreBreakdown", "recentActivity", "valuePerHour", "profileSummary",
]

# responseType is made here insteed of asking Claude to make it since analytics.py's function
# already include a fixed list/dict return shape per intent. This makes sure Claude doesn't need to
# also guess and prevents a second way for things to disagree
INTENT_RESPONSE_TYPES = {
    "mostPlayedGames": "list",
    "leastPlayedGames": "list",
    "recentActivity": "list",
    "profileSummary": "dict",
    "genreBreakdown": "dict",
    "valuePerHour": "dict",
    }

# This is shown by the caller created in Sprint 3, it shows whenever intent coems back as unsupported
FALLBACK_MESSAGE = (
    "I couldn't match that question to something PlayStats is able to answer yet. " \
    "Try asking about: your most played games, your least played games, genre breakdown, recent activity, " \
    "value per hour, or a summary of your profile."
    )

class IntentClassification(BaseModel):
    """
    Pydantic(included with Anthropic import) model passed as output_format to client.messages.parse(). The literal here
    is the JSON Schema enum, which makes sure that an out-of-scope intent becomes impossible 
    instead of a case that needs to become validated. "unsupported" is a 7th valid value so no match is a 
    normal classification and not a special case.
    """
    intent: Literal[
        "mostPlayedGames", "leastPlayedGames", "genreBreakdown", "recentActivity", "valuePerHour", "profileSummary",
        "unsupported",
        ]

SYSTEM_PROMPT = (
    "You are an intent classifier for PlayStats: a Steam stats app. Classify the user's questions into exactly one of: " \
    "mostPlayedGames (all-time hours, most played), leastPlayedGames (all-time-hours, fewest played, not about cost), " \
    "genreBreakdown (hours by genre), recentActivity (hours in the last two weeks specifically), valuePerHour (cost per " \
    "hour played, anything about money/value for money), profileSummary (persona name, avatar, library size, total hours). " \
    "If the question doesn't clearly match one of these listed, classify it as unsupported. Only classify. Do not answer the question " \
    "compute statistics or output any numbers."
)

def _classify_with_claude(question: str) -> str:
    """
    Calls Claude to classify one question and returns the raw intent string. Raises IntentRouterError on network failures and IntentClassificationError
    when Claude's output can't be trusted (i.e. failed parse, refusal etc.)
    """
    try:
        response = client.messages.parse(
            model=MODEL,
            max_tokens=200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": question}],
            output_format=IntentClassification,
        )
    except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.APIStatusError) as e:
        raise IntentRouterError(f"Request to Claude failed: {e}") from e

    if response.stop_reason == "refusal":
        raise IntentClassificationError("Claude declined to classify this question. Please try again.")
    if response.parsed_output is None:
        raise IntentClassificationError("Claude's response could not be parsed into a valid intent.")

    return response.parsed_output.intent

def route_intent(question: str) -> dict:
    """
    Classifies a free-text question into one of PlayStats' six supported intents, or "unsupported" if nothing matches.
    responseType is searched up locally instead of asked of Claude since it's already fully determined by analytics.py's
    fixed return shapes for each intent.
    """
    if not question or not question.strip():
        return {"intent": "unsupported", "responseType": None}

    intent = _classify_with_claude(question)

    return {
        "intent": intent,
        "responseType": INTENT_RESPONSE_TYPES.get(intent),
    }

def summarize_result(intent: str, data: dict | list) -> str | None:
    """
    Asks Claude to phrase a short, natural language summary of the already computer analytics data.
    Claude only restates the given numbers and never computer or is given the chance to invent any. Returns None on failure so
    the caller can still see the chart without a summary
    """
    system_prompt = (
        f"You are a PlayStats' analytics narrator. You're given the intent '{intent}' and the exact JSON data that was already " \
        "computed and charted for the user. Write a 3-5 sentence summary that explains what the chart shows, as if you are walking " \
        "the user through it.\n\n"
        "Rules:\n" \
        "Use ONLY the numbers and names present in the JSON. Do not calculate, estimate or invent a number that isn't in the data already. " \
        "When the data is a sorted list, the first entry is the most relevant one. (e.g. most hours played, or best value per hour) " \
        "unless the field names say otherwise.\n"
        "Call out the standout: the top entry, the biggest gap or the most notable comparison in the data.\n"
        "Write it like you're describing the chart to someone who hasn't seen it yet. in plain language not a restatement of the JSON structure " \
        "or field names.\n"
        "Do not give advice, recommendations or opinions."
    )

    try:
        response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=system_prompt,
        messages=[{"role": "user", "content": json.dumps(data)}],
        )
    except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.APIStatusError):
        return None

    if response.stop_reason == "refusal":
        return None

    text = "".join(block.text for block in response.content if block.type == "text").strip()
    return text or None
        
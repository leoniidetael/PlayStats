"""
A wrapper created around the Steam Web API endpoints PlayStats requires. For now only the Numeric SteamID64, the vanity URL
is being saved for later implementation.

AI usage: Claude (Anthropic) was used to identify a bug in get_owned_games, specifically a private/empty-profile bug where they were receiving
the same error code even though they are not the same errors. Claude was also used to debug Github repository ruleset/branch protection issues
I ran into. All code was written and commited by me (Leoniide Tael) and Claude was used for targeted debugging and to review code. Any code
suggestions were integrated by hand and adapted accordingly.
"""

# Imports
import os
import requests
from dotenv import load_dotenv
import json

# Function that reads in .env files and reads KEY=value line
load_dotenv()
API_KEY = os.getenv("STEAM_API_KEY")

# Base domain that will be built upon with f-strings
BASE_URL = "https://api.steampowered.com"

# Custom exceptions so the Streamlit layer can catch each case and display a user friendly message
# instead of a raw error message
class SteamAPIError(Exception):
    """
    Base class for all the errors raised by this module including network failures
    """

class InvalidSteamIDError(SteamAPIError):
    """
    Whenever the SteamID64 is malformed or there is no account matching the ID the error will be raised
    """

class PrivateProfileError(SteamAPIError):
    """
    Raised whenever the profile exists but the profile is private
    """

class EmptyProfileError(SteamAPIError):
    """
    Raised whenever a public profile has an empty game library
    """

CACHE_DIR = "cache"

def _cache_path(cache_key: str) -> str:
    """
    Creates the file path for a given cache key inside CACHE DIR
    """
    return os.path.join(CACHE_DIR, f"{cache_key}.json")

def _load_cache(cache_key: str) -> dict | None:
    """
    Returns cached data if it exists, otherwise return None
    """

    path = _cache_path(cache_key)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return None
    return None

def _save_cache(cache_key: str, data: dict) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_cache_path(cache_key), "w") as f:
        json.dump(data, f)

def _validate_steam_id(steam_id: str) -> None:
    """
    SteamID64s are always a 17 digit number, this catches all the bad inputs before an API call is used
    """

    if not str(steam_id).isdigit() or len(str(steam_id)) != 17:
        raise InvalidSteamIDError(f"'{steam_id}' is not a valid SteamID64, expected entry is 17 digits with no other characters.")

def _get(url: str, params: dict, cache_key: str | None = None) -> dict:
    """
    Shared requests/response handling. This catches network failures and checks the local JSON cache when a cache_key
    is  given and saves a successful response before it returns.
    """

    if cache_key:
        cached = _load_cache(cache_key)
        if cached is not None:
            return cached

    try:
        response = requests.get(url, params=params)
    except requests.exceptions.RequestException as e:
        raise SteamAPIError(f"Request to Steam API has failed: {e}") from e

    if response.status_code != 200:
        raise SteamAPIError(f"Steam API returned the status: {response.status_code} for {url}")

    data = response.json()

    if cache_key:
        _save_cache(cache_key, data)

    return data

def get_owned_games(steam_id: str) -> dict:
    """
    Returns the owned games payload for a SteamID64 including app info and playtime_forever per game
    """

    # Error handling
    _validate_steam_id(steam_id)

    # Raises PrivateProfileError/InvalidSteamIDError before empty games list is checked, this ensure a private profile get the right error 
    # instead of being mistaken for an empty profile
    get_player_summary(steam_id)

    # f-string that creates the full endpoint url with the BASE_URL, include specific Steam endpoint that returns a user's 
    # entire game library
    url = f"{BASE_URL}/IPlayerService/GetOwnedGames/v0001/"

    # Query string Steam expects and requests builds that string for me by passing a dict
    params = {
        "key": API_KEY,                     # Proves that the request is coming from registered app

        "steamid": steam_id,                # The library I'm asking for

        "include_appinfo": True,            # Ask that Steam also returns game names and icons not only the app IDs

        "include_played_free_games": True,  # Ensure free-to-play games don't get excluded

        "format": "json",                   # Get JSON returned instead of XML (Steam's default)
    }

    # Send the GET request to Steam's servers and wait for response
    data = _get(url, params, cache_key=f"owned_games_{steam_id}")

    # Error handling for when a profile/library is empty
    games = data.get("response", {}).get("games")
    if not games:
        raise EmptyProfileError(f"No games found for SteamID {steam_id}. Profile may have an empty library.")

    return data

def get_recently_played_games(steam_id: str) -> dict:
    """
    Returns games played in the last two weeks including the playtime_2weeks and playtime_forever per each game
    """

    # Error handling
    _validate_steam_id(steam_id)

    # The endpoint is one that is scoped only to recent activity compared to the endpoint of get_owned_games
    url = f"{BASE_URL}/IPlayerService/GetRecentlyPlayedGames/v0001/"

    params = {
        "key": API_KEY,
        "steamid": steam_id,
        "format": "json",
    }

    # There is no error handling/empty check here since no games played revently is a normal result not an error
    return _get(url, params, cache_key=f"recently_played_{steam_id}")

def get_top_games_by_playtime(steam_id: str, limit: int = 20) -> list:
    """
    Pulls owned games and returns the top N sorted playtime_forever in descending order. get_app_details() is called against this
    list instead of the full library to stay within rate limits
    """

    # Reuse the function from above instead of using duplicate API calls
    data = get_owned_games(steam_id)

    # Nest the list of games inside data["response"]["games"], also use .get with {}/[] ensures that it won't crash
    # if there is an empty structure, an empty list will be returned instead of an error
    games = data.get("response", {}).get("games", [])

    # For each game dict g sort by g["playtime_forever"] going back to 0 if the field is missing
    sorted_games = sorted(games, key=lambda g: g.get("playtime_forever", 0), reverse=True)

    # Slice the list to keep the first limit entries

    return sorted_games[:limit]


def get_player_summary(steam_id: str) -> dict:
    """
    Returns profile info (persona name, avatar, online status, etc.) for a SteamID64
    """

    # Error handling
    _validate_steam_id(steam_id)

    # Clarify the URL, it exists under ISteamUser instead of IPlayerService that has been used previously
    url = f"{BASE_URL}/ISteamUser/GetPlayerSummaries/v0002/"

    params = {
        "key": API_KEY,

        "steamids": steam_id,   # Plural variable name to support multiple IDs separated by commas

        "format": "json",
    }

    data = _get(url, params, cache_key=f"player_summary_{steam_id}")
    players = data.get("response", {}).get("players", [])

    # If the players list is empty there is no Steam account matching the SteamID64
    if not players:
        raise InvalidSteamIDError(f"No Steam account found SteamID {steam_id}")

    # communityvisibilitystate: 1 is private, 2 is friends only and 3 is public
    if players[0].get("communityvisibilitystate") != 3:
        raise PrivateProfileError(f"Profile for SteamID {steam_id} is not public.")

    return data
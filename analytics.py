from steam_client import (
    get_app_details,
    get_owned_games,
    get_player_summary,
    get_recently_played_games,
    get_top_games_by_playtime,
)

def _to_name_hours(games: list) -> list:
    """
    Reshapes the Steam game dicts into consistent shapes ({name, hours}) for the UI and Claude to consume easier.
    """
    return [
            {
                "name": g.get("name", "Unknown"),
                "hours": round(g.get("playtime_forever", 0) / 60, 1),
            }
            for g in games
        ]

def most_played_games(steam_id: str, limit: int = 5) -> list:
    """
    Returns the top limit games (default 5) for SteamID64 sorted by playtime_forever in descending order. Defaults to a small number
    because in general people play a few games at once instead of 10+. Its reshaped to names/hours in order to make it easier
    for the UI and Claude router to consume a consistent shape instead of raw data.
    """

    games = get_top_games_by_playtime(steam_id, limit=limit)

    return _to_name_hours(games)

def least_played_games(steam_id: str, limit: int = 5) -> list:
    """
    Returns the bottom limit games (default 5) for SteamID64 sorted by playtime_forever in ascending order. Games with 0 playtime_forever
    (never launched) are filtered out for this function since this is only for least played games not never played. Unplayed games are going 
    to be used for value-per-hour where it actually matters that a user bought a game but didn't play it.
    """

    games = get_owned_games(steam_id).get("response", {}).get("games", [])

    played = [g for g in games if g.get("playtime_forever", 0) > 0]

    sorted_games = sorted(played, key=lambda g: g.get("playtime_forever", 0))[:limit]

    return _to_name_hours(sorted_games)

def recent_activity(steam_id: str, limit: int = 5) -> list:
    """
    Returns games played in the last two weeks for SteamID64, sorted by playtime_2weeks in descending order. Each entry has
    both recent hours and total hours logged so the UI and Claude router can show recent activity with context instead of only recent hours.
    """

    games = get_recently_played_games(steam_id).get("response", {}).get("games", [])

    sorted_games = sorted(games, key=lambda g: g.get("playtime_2weeks", 0), reverse=True)[:limit]

    return [
        {
            "name": g.get("name", "Unknown"),
            "recent_hours": round(g.get("playtime_2weeks", 0) / 60, 1),
            "total_hours": round(g.get("playtime_forever", 0) / 60, 1),
        }
        for g in sorted_games
    ]

def profile_summary(steam_id: str) -> dict:
    """
    Returns the top level profile info for a SteamID6o4: name, avatar, library size and total hours across the library. It combines
    get_player_summary and get_owned_games so that the UI/Claude gets one payload instead of piecing together two calls itself
    """
    player = get_player_summary(steam_id).get("response", {}).get("players", [])[0]

    games = get_owned_games(steam_id).get("response", {}).get("games", [])

    total_hours = round(sum(g.get("playtime_forever", 0) for g in games) / 60, 1)

    return {
        "persona_name": player.get("personaname", "Unknown"),
        "avatar": player.get("avatarfull", ""),
        "game_count": len(games),
        "total_hours": total_hours,
    }

def genre_breakdown(steam_id: str, limit: int = 20) -> dict:
    """
    Returns the hours played grouped by genre for a SteamID64, based on the top limit games and has the same bound as
    get_top_games_by_playtime instead of the entire library which stays within the Store API's rate limit. A game can
    have multiple genres so the hours are counted towards each one. The genre data comes from the Steam's Store API and
    some information may not be avilable due to restrictions so the result will come with a disclaimer instead of claiming
    to be exact.
    """

    games = get_top_games_by_playtime(steam_id, limit=limit)

    minutes_by_genre = {}
    for g in games:
        details = get_app_details(g.get("appid"))
        if not details:
            continue

        minutes = g.get("playtime_forever", 0)
        for genre in details.get("genres", []):
            name = genre.get("description", "Unknown")
            minutes_by_genre[name] = minutes_by_genre.get(name, 0) + minutes

    breakdown = sorted(
        (
            {"genre": name, "hours": round(minutes / 60, 1)}
            for name, minutes in minutes_by_genre.items()
        ),
        key=lambda entry: entry["hours"],
        reverse=True,
    )

    return {
        "breakdown": breakdown,
        "disclaimer": "Genre data is estimated from available Steam metadata and may be incomplete or missing for some games.",
    }

def value_per_hour(steam_id: str, limit: int = 20) -> dict:
    """
    Returns the cost-per-hour for a SteamID64's owned games. Store API calls are evenely split between the most-played games
    (best-value candidates based off of get_top_games_by_playtime) and the never played games (money spent with zero return). This
    makes sure that both groups get represented within the same total call budget rather than depending on the order that
    Steam returns the library in. Free games / games with no price data default to 0 instead of being skipped. Also free to play games
    with microtransactions or transactions within games count as 0 right now. Game with 0 hours played have a None value instead of 0
    to avoid division by 0. There is a pricing discliamer since prices don't reflect sales, bundles or regional price differences.
    """

    half = limit // 2

    played = get_top_games_by_playtime(steam_id, limit=half)

    owned = get_owned_games(steam_id).get("response", {}).get("games", [])
    unplayed = [g for g in owned if g.get("playtime_forever", 0) == 0][: limit - half]

    games = played + unplayed

    entries = []
    for g in games: 
        details = get_app_details(g.get("appid"))
        if not details:
            continue

        price_overview = details.get("price_overview", {})
        cost = price_overview.get("final", 0) / 100 # Steam prices are in cents by default

        hours = round(g.get("playtime_forever", 0) / 60, 1)
        cost_per_hour = round(cost / hours, 2) if hours > 0 else None

        entries.append({
            "name": g.get("name", "Unknown"),
            "cost": cost,
            "hours": hours,
            "value_per_hour": cost_per_hour,
        })

    entries.sort(key=lambda e: (e["value_per_hour"] is None, e["value_per_hour"]))

    return {
        "games": entries,
        "disclaimer": "Pricing is estimated from the current Steam Store listings. Pricing may not reflefct sale, bundle, or regional prices.",
    }
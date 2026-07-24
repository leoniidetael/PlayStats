import streamlit as st

from steam_client import (
    get_player_summary,
    get_top_games_by_playtime,
    SteamAPIError,
    InvalidSteamIDError,
    PrivateProfileError,
    EmptyProfileError
)

# Application title
st.title("PlayStats")

# Text entry box
steam_id = st.text_input("Please enter your SteamID64")

# Fetch and display profile summary
if steam_id:
    try:
        profile_data = get_player_summary(steam_id)
        player = profile_data["response"]["players"][0]

        st.subheader(player["personaname"])
        st.image(player["avatarfull"])

        top_games = get_top_games_by_playtime(steam_id)

        st.subheader("Top Games by Playtime")
        st.dataframe([
            {
                "Game": g.get("name", "Unknown"),
                "Hours Played": round(g.get("playtime_forever", 0) / 60, 1),

            }
            for g in top_games
        ])

    except InvalidSteamIDError:
        st.error("Not a valid SteamID64. Please double check the ID format and try again. Expected input is only numbers and 17 characters.")
    except PrivateProfileError:
        st.error("This profile is private. PlayStats can only be used on public profiles.")
    except EmptyProfileError:
        st.error("This profile has no games to display.")
    except SteamAPIError:
        st.error("Couldn't reach the Steam API. Please try again later.")

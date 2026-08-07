import streamlit as st
import pandas as pd
import plotly.express as px

from analytics import (
    most_played_games,
    least_played_games,
    genre_breakdown,
    recent_activity,
    value_per_hour,
    profile_summary,
)
from steam_client import (
    resolve_steam_id,
    SteamAPIError,
    InvalidSteamIDError,
    PrivateProfileError,
    EmptyProfileError
)
from intent_router import (
    route_intent,
    summarize_result,
    FALLBACK_MESSAGE,
    IntentRouterError,
    IntentClassificationError,
)

st.set_page_config(page_title="PlayStats", layout="wide")

# Application title
st.title("PlayStats")

# Text entry box, keyed so Streamlit owns its state directly instead of manually
# shadowing it with a lagging value=/session_state round-trip (that round-trip is what
# caused needing to clear the box before retyping a new ID)
steam_id_input = st.text_input(
    "Please enter your SteamID64, vanity name, or profile link", key="steam_id_input"
)

# Track what was last resolved for, separate from Streamlit's own widget state, so
# can tell when the box changed to a genuinely different profile and clear the stale
# Ask PlayStats answer
if steam_id_input != st.session_state.get("last_steam_id_input", ""):
    st.session_state.pop("ask_result", None)
st.session_state.last_steam_id_input = steam_id_input

def _steam_error_message(e: SteamAPIError) -> str:
    if isinstance(e, InvalidSteamIDError):
        return "Could not find a Steam profile matching that SteamID64, vanity name, or profile link. Please double-check and try again."
    if isinstance(e, PrivateProfileError):
        return "This profile is private. PlayStats can only be used on public profiles."
    if isinstance(e, EmptyProfileError):
        return "This profile has no games to analyze and display."
    return "Could not reach the Steam API. Please try again in a moment."

def _hours_bar_chart(games: list, title: str) -> None:
    df = pd.DataFrame(games) # columns are name, hours
    
    fig = px.bar(df, x='hours', y='name', orientation='h', title=title)
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

def chart_genre_breakdown(data: dict) -> None:
    df = pd.DataFrame(data["breakdown"]) # columns are genre, hours
    fig = px.bar(df, x="genre", y="hours", title="Hours by Genre")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(data["disclaimer"])

def chart_recent_activity(games: list) -> None:
    df=pd.DataFrame(games) # columns are name, recent_hours, total_hours
    long_df = df.melt(
        id_vars="name",
        value_vars=["recent_hours", "total_hours"],
        var_name="period", value_name="hours",
    )
    long_df["period"] = long_df["period"].map(
        {"recent_hours": "Last Two Weeks", "total_hours": "All Time"}
    )
    fig = px.bar(long_df, x="name", y="hours", color="period", barmode="group", title="Recent vs Total Playtime")
    st.plotly_chart(fig, use_container_width=True)

def chart_value_per_hour(data: dict) -> None:
    games = data["games"]
    chartable = [g for g in games if g["value_per_hour"] is not None]
    unplayed = [g for g in games if g["value_per_hour"] is None]

    df = pd.DataFrame(chartable)
    fig = px.bar(df, x="name", y="value_per_hour", title="Cost per Hour Played")
    st.plotly_chart(fig, use_container_width=True)

    if unplayed:
        st.caption(f"{len(unplayed)} game(s) with 0 hours played are excluded from the chart above:")
        st.dataframe(pd.DataFrame(unplayed)[["name", "cost"]])

    st.caption(data["disclaimer"])

def render_profile_summary(data: dict) -> None:
    col_avatar, col_info = st.columns([1, 3])
    with col_avatar:
        st.image(data["avatar"])
    with col_info:
        st.subheader(data["persona_name"])
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Games Owned", data["game_count"])
        m2.metric("Total Hours", data["total_hours"])
        m3.metric("Steam Level", data["steam_level"])
        m4.metric("Badges", data["badge_count"])

INTENT_DISPATCH = {
    "mostPlayedGames": (most_played_games, lambda d: _hours_bar_chart(d, "Most Played Games")),
    "leastPlayedGames": (least_played_games, lambda d: _hours_bar_chart(d, "Least Played Games")),
    "genreBreakdown": (genre_breakdown, chart_genre_breakdown),
    "recentActivity": (recent_activity, chart_recent_activity),
    "valuePerHour": (value_per_hour, chart_value_per_hour),
    "profileSummary": (profile_summary, render_profile_summary),
}

SAMPLE_QUESTIONS = {
    "Most played games": "What are my most played games?",
    "Least played games": "What are my least played games?",
    "Genre breakdown": "What genres do I play the most?",
    "Recent activity": "What have I played in the last two weeks?",
    "Value per hour": "Which games give me the best value for my money?",
    "Profile summary": "Summarize my gaming profile"
}

def _resolve_ask(steam_id: str, question: str) -> dict:
    try:
        routed = route_intent(question)
    except IntentClassificationError:
        return {"kind": "error", "message": "Could not understand that question to classify it. Please rephrase it and try again."}
    except IntentRouterError:
        return {"kind": "error", "message": "Could not reach Claude to classify this question. Please try again in a moment."}

    intent = routed["intent"]
    if intent not in INTENT_DISPATCH:
        return {"kind": "fallback", "message": FALLBACK_MESSAGE}

    analytics_fn, chart_fn = INTENT_DISPATCH[intent]
    try:
        data = analytics_fn(steam_id)
        summary = summarize_result(intent, data)
    except SteamAPIError as e:
        return {"kind": "error", "message": _steam_error_message(e)}

    return {"kind": "result", "chart_fn": chart_fn, "data": data, "summary": summary}

def _render_ask_result(result: dict) -> None:
    if result["kind"] == "error":
        st.error(result["message"])
    elif result["kind"] == "fallback":
        st.info(result["message"])
    else:
        if result.get("summary"):
            st.write(result["summary"])
        result["chart_fn"](result["data"])

# Resolve the raw input (numeric ID, vanity name, or profile URL) once before anything else uses it
resolved_steam_id = None
if steam_id_input:
    try:
        resolved_steam_id = resolve_steam_id(steam_id_input)
    except SteamAPIError as e:
        st.error(_steam_error_message(e))

# Fetch and display profile summary
if resolved_steam_id:
    try:
        render_profile_summary(profile_summary(resolved_steam_id))
        _hours_bar_chart(most_played_games(resolved_steam_id, limit=10), "Top Ten Games by Playtime")
    except SteamAPIError as e:
        st.error(_steam_error_message(e))

    st.divider()
    st.subheader("Ask PlayStats")

    st.caption("Try one of these questions or type your own question pertaining to any of these topics below:")
    chip_cols = st.columns(len(SAMPLE_QUESTIONS))
    for col, (label, sample_quesion) in zip(chip_cols, SAMPLE_QUESTIONS.items()):
        if col.button(label):
            st.session_state["ask_question_input"] = sample_quesion

    with st.form("ask_form"):
        question = st.text_input("Ask a question about your library", key="ask_question_input")
        submitted = st.form_submit_button("Ask")

    if submitted and question.strip():
        st.session_state.ask_result = _resolve_ask(resolved_steam_id, question)

    result = st.session_state.get("ask_result")
    if result:
        _render_ask_result(result)
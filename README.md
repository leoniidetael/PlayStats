# PlayStats

In it's current state, PlayStats is a wrapper around the Steam Web API that allows you to look up a Steam user's profile and their top 20 most played games in order.

To use the program create a .env file with your Steam Web API key.
A Steam web API key can be accessed through this link: https://steamcommunity.com/dev/apikey

streamlit must be installed for the program to work. 

To access the numeric SteamID64 input requirement refer to this website:
https://steamid.io/lookup/76561198228235012
Any Steam account can be entered here and it will be converted to the correct format.

# AI Usage
Claude (Anthropic) was used during devlopment for:
- Indetifying a bug where private profiles were recognized as empty profiles
- Debugging GitHub repository ruleset/branch protection issues

All code was written and committed by me, Leoniide Tael. Claude's role was to issue targeted debugging and error fixes that were then adapted and integrated by hand.

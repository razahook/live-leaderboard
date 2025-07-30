import os
import json
import re
import requests
from datetime import datetime, timedelta

# Define the path for the JSON file to store Twitch overrides
OVERRIDE_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'twitch_overrides.json')

def load_twitch_overrides():
    """Loads Twitch overrides from a JSON file."""
    if not os.path.exists(OVERRIDE_FILE_PATH):
        return {}
    try:
        with open(OVERRIDE_FILE_PATH, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {OVERRIDE_FILE_PATH}. Returning empty overrides.")
        return {}
    except Exception as e:
        print(f"Error loading Twitch overrides file: {e}")
        return {}

def save_twitch_overrides(overrides):
    """Saves Twitch overrides to a JSON file."""
    try:
        with open(OVERRIDE_FILE_PATH, 'w') as f:
            json.dump(overrides, f, indent=4)
    except Exception as e:
        print(f"Error saving Twitch overrides file: {e}")

def extract_twitch_username(twitch_link):
    """Extract Twitch username from various Twitch link formats."""
    if not twitch_link:
        return None
    patterns = [
        r"apexlegendsstatus\.com/core/out\?type=twitch&id=([a-zA-Z0-9_]+)",
        r"(?:https?://)?(?:www\.)?twitch\.tv/([a-zA-Z0-9_]+)",
        r"([a-zA-Z0-9_]+)"  # Fallback for just usernames
    ]
    for pattern in patterns:
        match = re.search(pattern, twitch_link)
        if match:
            return match.group(1)
    return None

def strip_status_suffix(username):
    """
    Removes common status suffixes from Twitch usernames.
    E.g., 'RogueOffline' -> 'Rogue', 'ZeekoTV_In' -> 'ZeekoTV_'
    Works for any username ending with status words, with or without underscores.
    """
    status_suffixes = [
        "InMatch", "InLobby", "Offline", "Lobby", "In", "Match", "Playing", "History", "Performance"
    ]
    for status in status_suffixes:
        # Remove if username ends with status, optionally preceded by an underscore
        regex = re.compile(rf"(_)?{status}$", re.IGNORECASE)
        username = regex.sub('', username)
    return username
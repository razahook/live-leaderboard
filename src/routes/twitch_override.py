# src/routes/twitch_override.py
from flask import Blueprint, jsonify, request
import json
import os
from src.routes.twitch_integration import get_twitch_live_status, extract_twitch_username, twitch_live_cache
from src.cache_manager import leaderboard_cache

twitch_override_bp = Blueprint('twitch_override', __name__)

TWITCH_OVERRIDES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'twitch_overrides.json')

@twitch_override_bp.route('/twitch/override', methods=['POST'])
def add_twitch_override():
    if not request.is_json:
        return jsonify({"success": False, "message": "Request must be JSON"}), 400

    data = request.get_json()
    player_name = data.get('player_name')
    twitch_username = data.get('twitch_username')

    if not player_name or not twitch_username:
        return jsonify({"success": False, "message": "Player name and Twitch username are required"}), 400

    overrides = {}
    if os.path.exists(TWITCH_OVERRIDES_FILE):
        try:
            with open(TWITCH_OVERRIDES_FILE, 'r', encoding='utf-8') as f:
                overrides = json.load(f)
        except json.JSONDecodeError:
            overrides = {}
        except Exception as e:
            print(f"Error loading twitch_overrides.json: {e}")
            return jsonify({"success": False, "message": "Server error loading overrides"}), 500

    # Create the Twitch link - handle both username and full URL formats
    if twitch_username.startswith('http'):
        # Extract username from URL and normalize
        username = extract_twitch_username(twitch_username)
        if username:
            twitch_link = f"https://twitch.tv/{username}"
        else:
            twitch_link = twitch_username  # Fallback to original
    else:
        twitch_link = f"https://twitch.tv/{twitch_username}"
    
    overrides[player_name] = {"twitch_link": twitch_link}

    try:
        with open(TWITCH_OVERRIDES_FILE, 'w', encoding='utf-8') as f:
            json.dump(overrides, f, indent=4)
        
        # Clear caches to force refresh with new override
        twitch_live_cache["data"] = {}
        twitch_live_cache["last_updated"] = None
        leaderboard_cache.clear()
        
        # Immediately attempt to fetch live status for the new override
        username = extract_twitch_username(twitch_link)
        live_status_result = None
        if username:
            print(f"Immediately fetching live status for new override: {username}")
            try:
                live_status = get_twitch_live_status([username])
                if live_status and username in live_status:
                    live_status_result = live_status[username]
                    print(f"Live status for {username}: {live_status_result}")
                else:
                    print(f"No live status returned for {username}")
            except Exception as e:
                print(f"Error fetching immediate live status for {username}: {e}")
        
        response_data = {
            "success": True, 
            "message": "Twitch override saved successfully",
            "player_name": player_name,
            "twitch_link": twitch_link
        }
        
        # Include live status in response if available
        if live_status_result is not None:
            response_data["live_status"] = live_status_result
            
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"Error saving twitch_overrides.json: {e}")
        return jsonify({"success": False, "message": "Server error saving override"}), 500
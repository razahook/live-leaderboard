# src/routes/twitch_override.py
from flask import Blueprint, jsonify, request
import json
import os

twitch_override_bp = Blueprint('twitch_override', __name__)

TWITCH_OVERRIDES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'twitch_overrides.json')

@twitch_override_bp.route('/stream-override', methods=['POST'])
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

    overrides[player_name] = {"twitch_link": f"https://twitch.tv/{twitch_username}"}

    try:
        with open(TWITCH_OVERRIDES_FILE, 'w', encoding='utf-8') as f:
            json.dump(overrides, f, indent=4)
        return jsonify({"success": True, "message": "Twitch override saved successfully"}), 200
    except Exception as e:
        print(f"Error saving twitch_overrides.json: {e}")
        return jsonify({"success": False, "message": "Server error saving override"}), 500
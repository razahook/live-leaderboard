# src/routes/tracker_proxy.py
from flask import Blueprint, jsonify, request
import requests
import os

tracker_proxy_bp = Blueprint('tracker_proxy', __name__)

# IMPORTANT: Get your Tracker.gg API key from an environment variable for security
# For local testing, you can hardcode it here, but for deployment, use environment variables.
# Example: os.environ.get("TRACKER_GG_API_KEY", "YOUR_TRACKER_GG_API_KEY_HERE")
# SECURITY FIX: never hard-code API keys. Read from the environment instead.
# A helpful error message is logged if the variable is missing so developers
# know why requests are failing.
TRACKER_GG_API_KEY = os.getenv("TRACKER_GG_API_KEY", "")

if not TRACKER_GG_API_KEY:
    print("[WARNING] TRACKER_GG_API_KEY is not set. Requests to tracker.gg will fail with 401 errors.")

@tracker_proxy_bp.route('/tracker-stats', methods=['GET'])
def get_tracker_stats():
    """
    Proxies requests to the Tracker.gg Apex Legends API.
    Handles /profile/{platform}/{platformUserIdentifier} and /profile/{platform}/{platformUserIdentifier}/sessions
    """
    platform = request.args.get('platform')
    identifier = request.args.get('identifier')
    endpoint_type = request.args.get('type', 'profile') # 'profile' or 'sessions'

    if not platform or not identifier:
        return jsonify({"success": False, "message": "Platform and identifier are required."}), 400

    base_url = "https://public-api.tracker.gg/v2/apex/standard/profile"

    if endpoint_type == 'profile':
        tracker_url = f"{base_url}/{platform}/{identifier}"
    elif endpoint_type == 'sessions':
        tracker_url = f"{base_url}/{platform}/{identifier}/sessions"
    else:
        return jsonify({"success": False, "message": "Invalid endpoint type."}), 400

    headers = {
        "TRN-Api-Key": TRACKER_GG_API_KEY,
        "Accept": "application/json"
    }

    try:
        response = requests.get(tracker_url, headers=headers)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        return jsonify(response.json()), response.status_code
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error from Tracker.gg: {e.response.status_code} - {e.response.text}")
        return jsonify({"success": False, "message": f"Tracker.gg API error: {e.response.status_code} - {e.response.text}"}), e.response.status_code
    except requests.exceptions.RequestException as e:
        print(f"Request Error to Tracker.gg: {e}")
        return jsonify({"success": False, "message": f"Failed to connect to Tracker.gg API: {str(e)}"}), 500
    except Exception as e:
        print(f"Unexpected error in tracker_proxy: {e}")
        return jsonify({"success": False, "message": f"An unexpected server error occurred: {str(e)}"}), 500
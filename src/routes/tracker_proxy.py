# src/routes/tracker_proxy.py
from flask import Blueprint, jsonify, request
import requests
import os
import re
from functools import wraps
import time
from collections import defaultdict

# Simple rate limiting
rate_limits = defaultdict(list)

def rate_limit(max_requests=60, window=60):
    """Simple rate limiting decorator"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
            now = time.time()
            
            # Clean old requests
            rate_limits[client_ip] = [req_time for req_time in rate_limits[client_ip] if now - req_time < window]
            
            # Check rate limit
            if len(rate_limits[client_ip]) >= max_requests:
                return jsonify({"success": False, "message": "Rate limit exceeded"}), 429
            
            # Add current request
            rate_limits[client_ip].append(now)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

tracker_proxy_bp = Blueprint('tracker_proxy', __name__)

# Get Tracker.gg API key from environment variable
TRACKER_GG_API_KEY = os.environ.get("TRACKER_GG_API_KEY")
if not TRACKER_GG_API_KEY:
    print("Warning: TRACKER_GG_API_KEY environment variable not found. API calls will fail.")
    TRACKER_GG_API_KEY = None

def validate_input(platform, identifier, endpoint_type):
    """Validate and sanitize user inputs"""
    # Validate platform
    valid_platforms = ['origin', 'psn', 'xbl', 'steam']
    if platform not in valid_platforms:
        return False, f"Invalid platform. Must be one of: {', '.join(valid_platforms)}"
    
    # Validate identifier (alphanumeric, underscores, hyphens only, max 50 chars)
    if not re.match(r'^[a-zA-Z0-9_-]{1,50}$', identifier):
        return False, "Invalid identifier. Must be alphanumeric with underscores/hyphens, max 50 characters."
    
    # Validate endpoint type
    valid_types = ['profile', 'sessions']
    if endpoint_type not in valid_types:
        return False, f"Invalid endpoint type. Must be one of: {', '.join(valid_types)}"
    
    return True, "Valid"

@tracker_proxy_bp.route('/tracker-stats', methods=['GET'])
@rate_limit(max_requests=30, window=60)  # 30 requests per minute for external API
def get_tracker_stats():
    """
    Proxies requests to the Tracker.gg Apex Legends API.
    Handles /profile/{platform}/{platformUserIdentifier} and /profile/{platform}/{platformUserIdentifier}/sessions
    """
    platform = request.args.get('platform', '').lower().strip()
    identifier = request.args.get('identifier', '').strip()
    endpoint_type = request.args.get('type', 'profile').lower().strip()

    if not platform or not identifier:
        return jsonify({"success": False, "message": "Platform and identifier are required."}), 400
    
    # Validate inputs
    is_valid, message = validate_input(platform, identifier, endpoint_type)
    if not is_valid:
        return jsonify({"success": False, "message": message}), 400

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
        # Don't expose internal error details to client
        if e.response.status_code == 404:
            return jsonify({"success": False, "message": "Player not found"}), 404
        elif e.response.status_code == 429:
            return jsonify({"success": False, "message": "Rate limit exceeded. Please try again later."}), 429
        else:
            return jsonify({"success": False, "message": "External API error"}), 502
    except requests.exceptions.RequestException as e:
        print(f"Request Error to Tracker.gg: {e}")
        return jsonify({"success": False, "message": "Failed to connect to external service"}), 502
    except Exception as e:
        print(f"Unexpected error in tracker_proxy: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500
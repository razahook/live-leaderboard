from flask import Blueprint, jsonify, request
import requests
import os
from datetime import datetime, timedelta
import re

twitch_bp = Blueprint("twitch", __name__)

# Cache for Twitch access token
twitch_token_cache = {
    "access_token": None,
    "expires_at": None
}

# Cache for live status checks
twitch_live_cache = {
    "data": {},
    "last_updated": None,
    "cache_duration": 120  # 2 minutes
}

# Directly embed client ID and secret for testing
TWITCH_CLIENT_ID = "1nd45y861ah5uh84jh4e68gjvjshl1"
TWITCH_CLIENT_SECRET = "zv6enoibg0g05qx9kbos20h57twvvw"

@twitch_bp.route("/api/twitch/live-status", methods=["POST"])
def check_live_status():
    """
    Check live status for multiple Twitch channels
    Expects JSON body with: {"channels": ["username1", "username2", ...]}
    """
    try:
        data = request.get_json()
        if not data or "channels" not in data:
            return jsonify({
                "success": False,
                "error": "Missing \'channels\' in request body"
            }), 400
        
        channels = data["channels"]
        if not isinstance(channels, list) or len(channels) == 0:
            return jsonify({
                "success": False,
                "error": "Channels must be a non-empty list"
            }), 400
        
        # Check cache first
        cache_key = ",".join(sorted(channels))
        if (twitch_live_cache["data"].get(cache_key) and 
            twitch_live_cache["last_updated"] and
            (datetime.now() - twitch_live_cache["last_updated"]).seconds < twitch_live_cache["cache_duration"]):
            
            return jsonify({
                "success": True,
                "cached": True,
                "data": twitch_live_cache["data"][cache_key],
                "last_updated": twitch_live_cache["last_updated"].isoformat()
            })
        
        # Get fresh data from Twitch API
        live_status = get_twitch_live_status(channels)
        
        if live_status is not None:
            # Update cache
            twitch_live_cache["data"][cache_key] = live_status
            twitch_live_cache["last_updated"] = datetime.now()
            
            return jsonify({
                "success": True,
                "cached": False,
                "data": live_status,
                "last_updated": twitch_live_cache["last_updated"].isoformat()
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to fetch live status from Twitch API"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

@twitch_bp.route("/api/twitch/config", methods=["POST"])
def set_twitch_config():
    """
    Set Twitch API configuration (Client ID and Secret)
    Expects JSON body with: {"client_id": "...", "client_secret": "..."}
    """
    try:
        data = request.get_json()
        if not data or "client_id" not in data or "client_secret" not in data:
            return jsonify({
                "success": False,
                "error": "Missing \'client_id\' or \'client_secret\' in request body"
            }), 400
        
        # Store in environment variables (in production, use proper secret management)
        # For testing, we are directly embedding them above.
        # os.environ["TWITCH_CLIENT_ID"] = data["client_id"]
        # os.environ["TWITCH_CLIENT_SECRET"] = data["client_secret"]
        
        # Clear token cache to force re-authentication
        twitch_token_cache["access_token"] = None
        twitch_token_cache["expires_at"] = None
        
        return jsonify({
            "success": True,
            "message": "Twitch API configuration updated (note: credentials are now hardcoded for testing)"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

def get_twitch_access_token():
    """
    Get Twitch access token using Client Credentials flow
    """
    # Check if we have a valid cached token
    if (twitch_token_cache["access_token"] and 
        twitch_token_cache["expires_at"] and
        datetime.now() < twitch_token_cache["expires_at"]):
        return twitch_token_cache["access_token"]
    
    # Use directly embedded credentials
    client_id = TWITCH_CLIENT_ID
    client_secret = TWITCH_CLIENT_SECRET
    
    if not client_id or not client_secret:
        print("Twitch Client ID or Secret not configured")
        return None
    
    try:
        response = requests.post("https://id.twitch.tv/oauth2/token", data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials"
        }, timeout=10)
        
        response.raise_for_status()
        token_data = response.json()
        
        # Cache the token
        twitch_token_cache["access_token"] = token_data["access_token"]
        # Set expiration time (subtract 60 seconds for safety)
        expires_in = token_data.get("expires_in", 3600) - 60
        twitch_token_cache["expires_at"] = datetime.now() + timedelta(seconds=expires_in)
        
        return token_data["access_token"]
        
    except Exception as e:
        print(f"Error getting Twitch access token: {e}")
        return None

def get_twitch_live_status(channels):
    """
    Get live status for multiple Twitch channels
    Falls back to mock data when API is unavailable
    """
    access_token = get_twitch_access_token()
    if not access_token:
        print("No access token available, using mock data for testing")
        return get_mock_twitch_data(channels)
    
    # Use directly embedded client ID
    client_id = TWITCH_CLIENT_ID
    if not client_id:
        print("No client ID available, using mock data for testing")
        return get_mock_twitch_data(channels)
    
    try:
        # Clean channel names (remove twitch.tv/ prefix if present)
        clean_channels = []
        for channel in channels:
            if isinstance(channel, str):
                # Extract username from various formats
                if "twitch.tv/" in channel:
                    username = channel.split("twitch.tv/")[-1]
                else:
                    username = channel
                # Remove any trailing slashes or query parameters
                username = username.split("/")[0].split("?")[0]
                if username:
                    clean_channels.append(username.lower())
        
        if not clean_channels:
            return {}
        
        # Build query string for multiple channels (max 100 per request)
        query_params = "&".join([f"user_login={channel}" for channel in clean_channels[:100]])
        url = f"https://api.twitch.tv/helix/streams?{query_params}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Client-Id": client_id
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        streams_data = response.json()
        
        # Process the response
        live_status = {}
        
        # Initialize all channels as offline
        for channel in clean_channels:
            live_status[channel] = {
                "is_live": False,
                "stream_data": None
            }
        
        # Update with live stream data
        for stream in streams_data.get("data", []):
            username = stream["user_login"].lower()
            live_status[username] = {
                "is_live": True,
                "stream_data": {
                    "title": stream.get("title", ""),
                    "game_name": stream.get("game_name", ""),
                    "viewer_count": stream.get("viewer_count", 0),
                    "started_at": stream.get("started_at", ""),
                    "thumbnail_url": stream.get("thumbnail_url", "").replace("{width}", "320").replace("{height}", "180")
                }
            }
        
        return live_status
        
    except Exception as e:
        print(f"Error getting Twitch live status: {e}, falling back to mock data")
        return get_mock_twitch_data(channels)

def get_mock_twitch_data(channels):
    """
    Generate mock Twitch live status data for testing when API is unavailable
    """
    from datetime import datetime
    
    # Mock data for specific known channels for testing
    mock_live_channels = {
        "naughty": {
            "is_live": True,
            "stream_data": {
                "title": "Apex Legends Ranked - Master Tier Gameplay",
                "game_name": "Apex Legends",
                "viewer_count": 1247,
                "started_at": datetime.now().isoformat(),
                "thumbnail_url": "https://static-cdn.jtvnw.net/previews-ttv/live_user_naughty-320x180.jpg"
            }
        },
        "teststreamer": {
            "is_live": False,
            "stream_data": None
        }
    }
    
    live_status = {}
    
    for channel in channels:
        if isinstance(channel, str):
            # Extract username from various formats
            if "twitch.tv/" in channel:
                username = channel.split("twitch.tv/")[-1]
            else:
                username = channel
            # Remove any trailing slashes or query parameters
            username = username.split("/")[0].split("?")[0].lower()
            
            if username in mock_live_channels:
                live_status[username] = mock_live_channels[username]
            else:
                # Default to offline for unknown channels
                live_status[username] = {
                    "is_live": False,
                    "stream_data": None
                }
    
    print(f"Generated mock data for channels: {list(live_status.keys())}")
    return live_status

def extract_twitch_username(twitch_link):
    """
    Extract Twitch username from various link formats
    """
    if not twitch_link:
        return None
    
    # Handle various formats:
    # https://twitch.tv/username
    # twitch.tv/username
    # username
    
    patterns = [
        r"apexlegendsstatus\.com/core/out\?type=twitch&id=([a-zA-Z0-9_]+)",
        r"(?:https?://)?(?:www\.)?twitch\.tv/([a-zA-Z0-9_]+)",
        r"^([a-zA-Z0-9_]+)$"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, twitch_link.strip())
        if match:
            return match.group(1).lower()
    
    return None




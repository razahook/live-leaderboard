import requests
import time
import json
import os
from flask import Blueprint, jsonify, request
from urllib.parse import quote_plus
from .twitch_integration import get_twitch_access_token, load_cache_file, save_cache_file


twitch_clips_bp = Blueprint('twitch_clips', __name__)

CLIPS_CACHE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache', 'twitch', 'clips.json')
twitch_clips_cache = {}

def get_twitch_user_id(username):
    """Get Twitch user ID for a username"""
    try:
        access_token = get_twitch_access_token()
        if not access_token:
            return None
            
        client_id = os.environ.get('TWITCH_CLIENT_ID')
        if not client_id:
            return None
            
        headers = {
            'Client-ID': client_id,
            'Authorization': f'Bearer {access_token}'
        }
        
        response = requests.get(f'https://api.twitch.tv/helix/users?login={username}', headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get('data'):
                return data['data'][0]['id']
        return None
    except Exception as e:
        print(f"Error getting user ID for {username}: {e}")
        return None

def get_user_clips_cached(username, headers, limit=5):
    cache_key = f"clips_{username}"
    if cache_key in twitch_clips_cache:
        entry = twitch_clips_cache[cache_key]
        if time.time() - entry['timestamp'] < 3600:
            return entry['data']
    cache_data = load_cache_file(CLIPS_CACHE)
    if 'clips' not in cache_data:
        cache_data['clips'] = {}
    if username in cache_data['clips']:
        entry = cache_data['clips'][username]
        if time.time() - entry['timestamp'] < 3600:
            twitch_clips_cache[cache_key] = entry
            return entry['data']
    try:
        user_response = requests.get(
            f"https://api.twitch.tv/helix/users?login={quote_plus(username)}",
            headers=headers
        )
        if user_response.status_code != 200:
            result = {"has_clips": False, "recent_clips": []}
        else:
            user_data = user_response.json()
            if not user_data.get("data"):
                result = {"has_clips": False, "recent_clips": []}
            else:
                user_id = user_data["data"][0]["id"]
                response = requests.get(
                    f"https://api.twitch.tv/helix/clips?broadcaster_id={user_id}&first={limit}",
                    headers=headers
                )
                if response.status_code == 200:
                    data = response.json()
                    clips = data.get('data', [])
                    formatted_clips = []
                    for clip in clips:
                        formatted_clips.append({
                            'id': clip['id'],
                            'url': clip['url'],
                            'embed_url': clip['embed_url'],
                            'title': clip['title'],
                            'view_count': clip['view_count'],
                            'created_at': clip['created_at'],
                            'duration': clip['duration'],
                            'thumbnail_url': clip['thumbnail_url']
                        })
                    result = {
                        "has_clips": len(clips) > 0,
                        "recent_clips": formatted_clips[:limit]
                    }
                else:
                    result = {"has_clips": False, "recent_clips": []}
        twitch_clips_cache[cache_key] = {
            'data': result,
            'timestamp': time.time()
        }
        if 'clips' not in cache_data:
            cache_data['clips'] = {}
        cache_data['clips'][username] = {
            'data': result,
            'timestamp': time.time()
        }
        save_cache_file(CLIPS_CACHE, cache_data)
        return result
    except Exception as e:
        result = {"has_clips": False, "recent_clips": []}
        twitch_clips_cache[cache_key] = {
            'data': result,
            'timestamp': time.time()
        }
        return result

@twitch_clips_bp.route('/stream-clips/<username>')
def get_user_clips(username):
    try:
        token = get_twitch_access_token()
        if not token:
            return jsonify({"success": False, "error": "Failed to get Twitch access token"}), 500
        headers = {
            'Client-ID': os.environ.get('TWITCH_CLIENT_ID'),
            'Authorization': f'Bearer {token}'
        }
        clips_data = get_user_clips_cached(username, headers)
        return jsonify({"success": True, "data": clips_data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@twitch_clips_bp.route('/stream-clips/create/<username>', methods=['POST'])
def create_clip(username):
    """Create a clip of the user's current live stream"""
    try:
        # Try to get user access token first (for clip creation)
        from .twitch_oauth import get_user_access_token
        
        access_token = None
        token_type = "app"
        
        # Check if we have a user access token for this user or any authorized user
        try:
            # First try the specific username
            access_token = get_user_access_token(username)
            if access_token:
                token_type = "user"
            else:
                # Try to get any authorized user token (for creating clips of other streamers)
                from .twitch_oauth import user_tokens
                for auth_username, token_info in user_tokens.items():
                    import time
                    if time.time() - token_info['created_at'] < token_info['expires_in']:
                        access_token = token_info['access_token']
                        token_type = "user"
                        print(f"Using {auth_username}'s token to create clip of {username}")
                        break
        except ImportError:
            # OAuth module not available, fall back to app token
            pass
        
        # Fall back to app access token if no user token available
        if not access_token:
            access_token = get_twitch_access_token()
            if not access_token:
                return jsonify({"success": False, "error": "Failed to get Twitch access token"}), 500
        
        client_id = os.environ.get('TWITCH_CLIENT_ID')
        if not client_id:
            return jsonify({"success": False, "error": "Missing Twitch client ID"}), 500
        
        # Get user ID
        user_id = get_twitch_user_id(username)
        if not user_id:
            return jsonify({"success": False, "error": f"Could not find Twitch user: {username}"}), 404
        
        headers = {
            'Client-ID': client_id,
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Check if user is currently live
        stream_response = requests.get(f'https://api.twitch.tv/helix/streams?user_id={user_id}', headers=headers)
        if stream_response.status_code != 200:
            return jsonify({"success": False, "error": "Failed to check stream status"}), 500
        
        stream_data = stream_response.json()
        if not stream_data.get('data'):
            return jsonify({"success": False, "error": f"{username} is not currently live"}), 400
        
        # Create the clip
        clip_data = {
            "broadcaster_id": user_id,
            "has_delay": False  # Set to True if you want to account for stream delay
        }
        
        clip_response = requests.post(
            'https://api.twitch.tv/helix/clips',
            headers=headers,
            json=clip_data
        )
        
        if clip_response.status_code == 202:  # Accepted
            clip_result = clip_response.json()
            if clip_result.get('data'):
                clip_info = clip_result['data'][0]
                return jsonify({
                    "success": True,
                    "message": f"Clip created successfully for {username}!",
                    "data": {
                        "clip_id": clip_info['id'],
                        "edit_url": clip_info['edit_url'],
                        "url": f"https://clips.twitch.tv/{clip_info['id']}",
                        "embed_url": f"https://clips.twitch.tv/embed?clip={clip_info['id']}",
                        "broadcaster": username,
                        "token_type": token_type
                    }
                })
        elif clip_response.status_code == 401:
            return jsonify({
                "success": False,
                "error": "Authentication required",
                "error_type": "auth_required",
                "message": f"Need user authorization to create clips. Using {token_type} token.",
                "auth_url": "/api/session/start"
            }), 401
        elif clip_response.status_code == 403:
            return jsonify({
                "success": False,
                "error": "Insufficient permissions",
                "error_type": "insufficient_scope",
                "message": "User needs to authorize clip creation permissions.",
                "auth_url": "/api/session/start"
            }), 403
        
        return jsonify({
            "success": False, 
            "error": f"Failed to create clip: {clip_response.status_code} - {clip_response.text}",
            "token_type": token_type
        }), 500
        
    except Exception as e:
        return jsonify({"success": False, "error": f"Error creating clip: {str(e)}"}), 500

@twitch_clips_bp.route('/stream-clips/batch', methods=['POST'])
def get_clips_batch():
    try:
        data = request.get_json()
        usernames = data.get('usernames', [])
        if not usernames:
            return jsonify({"success": False, "error": "No usernames provided"}), 400
        token = get_twitch_access_token()
        if not token:
            return jsonify({"success": False, "error": "Failed to get Twitch access token"}), 500
        headers = {
            'Client-ID': os.environ.get('TWITCH_CLIENT_ID'),
            'Authorization': f'Bearer {token}'
        }
        results = {}
        for username in usernames:
            clips_data = get_user_clips_cached(username, headers)
            results[username] = clips_data
        return jsonify({"success": True, "data": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
import requests
import time
import json
import os
from datetime import datetime
from flask import Blueprint, jsonify, request
from urllib.parse import quote_plus
from routes.twitch_integration import get_twitch_access_token
from routes.supabase_client import get_supabase
try:
    from vercel_cache import VercelCacheManager
    cache_manager = VercelCacheManager()
    # Legacy compatibility functions
    def load_cache_file(file_path):
        if 'clips' in file_path:
            return cache_manager.load_initial_cache('clips')
        return {}
    
    def save_cache_file(file_path, data):
        # In Vercel, just log - actual persistence would use Redis/KV
        print(f"Cache save attempt: {file_path}")
except ImportError:
    from routes.twitch_integration import load_cache_file, save_cache_file


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


def _resolve_streamer_id(supabase_client, twitch_login: str):
    """Find or create a streamer row and return its id. Best-effort; returns None on failure."""
    try:
        if supabase_client is None or not twitch_login:
            return None
        login = twitch_login.lower()
        res = supabase_client.table('streamers').select('id').eq('twitch_login', login).limit(1).execute()
        if res.data:
            return res.data[0]['id']
        # Create minimal row
        ins = supabase_client.table('streamers').insert({
            'twitch_login': login,
            'twitch_display_name': None,
            'twitch_id': None,
            'medal_username': None,
            'apex_names': [],
            'country_code': None,
            'profile_image_url': None
        }).execute()
        if ins.data:
            return ins.data[0]['id']
    except Exception as e:
        print(f"Streamer resolve failed for {twitch_login}: {e}")
    return None


def _save_clip_metadata(clip_id: str, username: str, edit_url: str, url: str, embed_url: str, creator_login: str = None, created_by_user_id: str = None):
    """Persist clip metadata to database. Best-effort, non-blocking."""
    try:
        # Try Supabase first
        sb = get_supabase()
        if sb is not None:
            try:
                streamer_id = _resolve_streamer_id(sb, username)
                extra = {}
                if creator_login:
                    extra['creator_login'] = creator_login
                if created_by_user_id:
                    extra['created_by_user_id'] = created_by_user_id
                payload = {
                    'source': 'twitch',
                    'external_id': clip_id,
                    'url': url,
                    'embed_url': embed_url,
                    'edit_url': edit_url,
                    'broadcaster_login': username.lower(),
                    'creator_login': creator_login,
                    'created_by_user_id': created_by_user_id,
                    'streamer_id': streamer_id,
                    'title': None,  # Would need to fetch from Twitch API
                    'duration': None,  # Would need to fetch from Twitch API  
                    'view_count': None,  # Would need to fetch from Twitch API
                    'thumbnail_url': None,  # Would need to fetch from Twitch API
                    'extra': extra,
                }
                # Upsert by external_id to avoid dupes
                sb.table('clips').upsert(payload, on_conflict='external_id').execute()
                print(f"✅ Clip saved to Supabase: {clip_id}")
                return
            except Exception as e:
                print(f"Supabase clip save failed: {e}")
        
        # Fallback to local database
        try:
            from models.clips import Clip
            from models.user import db
            
            # Check if clip already exists
            existing_clip = Clip.query.filter_by(external_id=clip_id).first()
            if existing_clip:
                # Update existing clip
                existing_clip.url = url
                existing_clip.embed_url = embed_url
                existing_clip.edit_url = edit_url
                existing_clip.updated_at = datetime.utcnow()
                if creator_login:
                    existing_clip.creator_login = creator_login
                if created_by_user_id:
                    existing_clip.created_by_user_id = created_by_user_id
            else:
                # Create new clip
                new_clip = Clip(
                    external_id=clip_id,
                    source='twitch',
                    url=url,
                    embed_url=embed_url,
                    edit_url=edit_url,
                    broadcaster_login=username.lower(),
                    creator_login=creator_login,
                    created_by_user_id=created_by_user_id
                )
                db.session.add(new_clip)
            
            db.session.commit()
            print(f"✅ Clip saved to local database: {clip_id}")
            
        except Exception as e:
            print(f"Local database clip save failed: {e}")
            
    except Exception as e:
        print(f"Clip save failed: {e}")

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
        from routes.twitch_oauth import get_user_access_token
        
        access_token = None
        token_type = "app"
        
        # Check if we have any user access token with clips:edit scope
        try:
            # First try the specific broadcaster's token
            access_token = get_user_access_token(username)
            if access_token:
                token_type = "user"
                print(f"Using {username}'s own token to create clip")
            else:
                # Try to get any authorized user token from Supabase
                try:
                    from routes.supabase_client import get_supabase
                    sb = get_supabase()
                    if sb is not None:
                        # Get all valid tokens from Supabase
                        import time
                        current_time = time.time()
                        result = sb.table('user_tokens').select('*').execute()
                        
                        for token_info in result.data or []:
                            if current_time - token_info['created_at'] < token_info['expires_in']:
                                access_token = token_info['access_token']
                                token_type = "user"
                                print(f"Using {token_info['username']}'s token to create clip of {username}")
                                break
                except Exception as e:
                    print(f"Error loading tokens from Supabase: {e}")
                    
                # Fallback to in-memory tokens
                if not access_token:
                    from routes.twitch_oauth import user_tokens
                    for auth_username, token_info in user_tokens.items():
                        import time
                        if time.time() - token_info['created_at'] < token_info['expires_in']:
                            access_token = token_info['access_token']
                            token_type = "user"
                            print(f"Using {auth_username}'s token to create clip of {username}")
                            break
        except ImportError:
            # OAuth module not available
            pass
        
        # Clip creation REQUIRES user token with clips:edit scope - app tokens cannot create clips
        if not access_token:
            return jsonify({
                "success": False,
                "error": "User authentication required",
                "error_type": "auth_required", 
                "message": "Creating clips requires user authorization with clips:edit scope. App tokens cannot create clips.",
                "auth_url": "/api/session/start"
            }), 401
        
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
        
        # Add detailed logging for debugging
        print(f"🔍 Clip API Response Status: {clip_response.status_code}")
        print(f"🔍 Clip API Response Headers: {dict(clip_response.headers)}")
        print(f"🔍 Clip API Response Body: {clip_response.text}")
        
        if clip_response.status_code == 202:  # Twitch returns 202 Accepted for successful clip creation
            clip_result = clip_response.json()
            if clip_result.get('data'):
                clip_info = clip_result['data'][0]
                
                # Twitch returns the clip ID and edit_url
                clip_id = clip_info.get('id')
                edit_url = clip_info.get('edit_url', f"https://clips.twitch.tv/{clip_id}/edit")
                
                if not clip_id:
                    print(f"❌ No clip ID returned from Twitch: {clip_result}")
                    return jsonify({
                        "success": False,
                        "error": "Clip creation failed - no clip ID returned from Twitch"
                    }), 500
                
                # Save clip metadata to database
                try:
                    # Determine creator login from the authenticated user who made the request
                    creator_login = request.args.get('as')  # From frontend
                    if not creator_login:
                        # Try to get from any authenticated user token we used
                        try:
                            from routes.twitch_oauth import user_tokens
                            # Find which user's token was used (if any)
                            for auth_username, token_data in user_tokens.items():
                                import time
                                if time.time() - token_data['created_at'] < token_data['expires_in']:
                                    if token_data.get('access_token') == access_token.split()[-1] if ' ' in access_token else access_token:
                                        creator_login = auth_username
                                        break
                            
                            # Also check Supabase for the creator
                            if not creator_login:
                                sb = get_supabase()
                                if sb is not None:
                                    result = sb.table('user_tokens').select('*').execute()
                                    for token_info in result.data or []:
                                        if token_info.get('access_token') == access_token:
                                            creator_login = token_info.get('username')
                                            break
                        except Exception as e:
                            print(f"Could not determine creator from token: {e}")
                    
                    _save_clip_metadata(
                        clip_id=clip_id,
                        username=username,
                        edit_url=edit_url,
                        url=f"https://clips.twitch.tv/{clip_id}",
                        embed_url=f"https://clips.twitch.tv/embed?clip={clip_id}",
                        creator_login=creator_login,
                        created_by_user_id=request.headers.get('X-User-Id') or None
                    )
                    print(f"✅ Clip created successfully: {clip_id}")
                except Exception as e:
                    print(f"Failed to save clip metadata: {e}")

                return jsonify({
                    "success": True,
                    "message": f"Clip created successfully for {username}!",
                    "data": {
                        "clip_id": clip_id,
                        "edit_url": edit_url,
                        "url": f"https://clips.twitch.tv/{clip_id}",
                        "embed_url": f"https://clips.twitch.tv/embed?clip={clip_id}",
                        "broadcaster": username,
                        "token_type": token_type
                    }
                })
            else:
                print(f"❌ No data in clip creation response: {clip_result}")
                return jsonify({
                    "success": False,
                    "error": "Clip creation failed - no clip data returned from Twitch"
                }), 500
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
        else:
            # Log unexpected responses for debugging
            print(f"❌ Unexpected clip response status: {clip_response.status_code}")
            print(f"❌ Response body: {clip_response.text}")
            return jsonify({
                "success": False, 
                "error": f"Failed to create clip: {clip_response.status_code} - {clip_response.text}",
                "token_type": token_type,
                "debug_info": {
                    "status_code": clip_response.status_code,
                    "response_body": clip_response.text[:500],  # Limit to avoid huge responses
                    "headers": dict(clip_response.headers)
                }
            }), 500
        
    except Exception as e:
        return jsonify({"success": False, "error": f"Error creating clip: {str(e)}"}), 500

@twitch_clips_bp.route('/saved-clips', methods=['GET'])
def get_saved_clips():
    """Get all saved clips from database"""
    try:
        sb = get_supabase()
        if sb is None:
            return jsonify({"success": False, "error": "Database not available"}), 500
        
        # Get all clips from database
        result = sb.table('clips').select('*').order('created_at', desc=True).limit(100).execute()
        
        if result.data:
            return jsonify({
                "success": True,
                "data": {
                    "clips": result.data,
                    "count": len(result.data),
                    "source": "database"
                }
            })
        else:
            return jsonify({
                "success": True,
                "data": {
                    "clips": [],
                    "count": 0,
                    "source": "database",
                    "message": "No saved clips found"
                }
            })
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@twitch_clips_bp.route('/saved-clips/<username>', methods=['GET'])
def get_saved_clips_for_streamer(username):
    """Get saved clips for a specific streamer"""
    try:
        sb = get_supabase()
        if sb is None:
            return jsonify({"success": False, "error": "Database not available"}), 500
        
        # Get clips for specific broadcaster
        result = sb.table('clips').select('*').eq('broadcaster_login', username.lower()).order('created_at', desc=True).limit(50).execute()
        
        if result.data:
            return jsonify({
                "success": True,
                "data": {
                    "clips": result.data,
                    "count": len(result.data),
                    "source": "database",
                    "streamer": username
                }
            })
        else:
            return jsonify({
                "success": True,
                "data": {
                    "clips": [],
                    "count": 0,
                    "source": "database",
                    "streamer": username,
                    "message": f"No saved clips found for {username}"
                }
            })
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@twitch_clips_bp.route('/my-clips', methods=['GET'])
def get_my_clips():
    """Get clips created by the current user (requires authentication)"""
    try:
        # Check for user authentication via query parameter or session
        username = request.args.get('username')
        if not username:
            return jsonify({
                "success": True,
                "data": {
                    "clips": [],
                    "count": 0,
                    "source": "user",
                    "message": "User authentication required"
                }
            })
        
        # Verify user is authenticated - check both in-memory and Supabase
        from routes.twitch_oauth import user_tokens
        token_info = None
        
        # First check in-memory cache
        if username in user_tokens:
            token_info = user_tokens[username]
            # Check if token is still valid
            import time
            if time.time() - token_info['created_at'] >= token_info['expires_in']:
                token_info = None
        
        # If not in memory or expired, check Supabase
        if not token_info:
            try:
                sb = get_supabase()
                if sb is not None:
                    result = sb.table('user_tokens').select('*').eq('username', username).limit(1).execute()
                    if result.data:
                        stored_token = result.data[0]
                        # Check if token is still valid
                        import time
                        if time.time() - stored_token['created_at'] < stored_token['expires_in']:
                            token_info = stored_token
                            # Cache in memory for future use
                            user_tokens[username] = token_info
                        else:
                            print(f"Token for {username} has expired")
                            # Clean up expired token
                            sb.table('user_tokens').delete().eq('username', username).execute()
            except Exception as e:
                print(f"Error loading token from Supabase for {username}: {e}")
        
        # If still no valid token found
        if not token_info:
            return jsonify({
                "success": True,
                "data": {
                    "clips": [],
                    "count": 0,
                    "source": "user",
                    "message": "User authentication required"
                }
            })
        
        # Get clips from Supabase database for this user
        sb = get_supabase()
        if sb is None:
            return jsonify({"success": False, "error": "Database not available"}), 500
        
        # Query clips created by this user
        result = sb.table('clips').select('*').eq('creator_login', username).order('created_at', desc=True).limit(50).execute()
        
        clips = result.data if result.data else []
        
        return jsonify({
            "success": True,
            "data": {
                "clips": clips,
                "count": len(clips),
                "source": "user",
                "username": username,
                "message": f"Found {len(clips)} clips created by {username}" if clips else "No clips created yet"
            }
        })
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@twitch_clips_bp.route('/favorites', methods=['GET'])
def get_user_favorites():
    """Get user's favorite clips (requires authentication)"""
    try:
        # In a real implementation, you'd get user_id from JWT/session
        # For now, return example structure
        return jsonify({
            "success": True,
            "data": {
                "favorites": [],
                "count": 0,
                "source": "favorites",
                "message": "User authentication required to view favorites"
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@twitch_clips_bp.route('/favorites/<clip_id>', methods=['POST'])
def add_favorite(clip_id):
    """Add a clip to user's favorites (requires authentication)"""
    try:
        sb = get_supabase()
        if sb is None:
            return jsonify({"success": False, "error": "Database not available"}), 500
        
        # In a real implementation, get user_id from JWT token
        # For now, return auth required message
        return jsonify({
            "success": False, 
            "error": "Authentication required",
            "message": "You must be logged in to add favorites"
        }), 401
        
        # Real implementation would be:
        # user_id = get_current_user_id()  # From JWT/session
        # sb.table('favorites').insert({
        #     'user_id': user_id,
        #     'clip_id': clip_id
        # }).execute()
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@twitch_clips_bp.route('/favorites/<clip_id>', methods=['DELETE'])
def remove_favorite(clip_id):
    """Remove a clip from user's favorites (requires authentication)"""
    try:
        sb = get_supabase()
        if sb is None:
            return jsonify({"success": False, "error": "Database not available"}), 500
        
        # In a real implementation, get user_id from JWT token
        # For now, return auth required message
        return jsonify({
            "success": False, 
            "error": "Authentication required",
            "message": "You must be logged in to remove favorites"
        }), 401
        
        # Real implementation would be:
        # user_id = get_current_user_id()  # From JWT/session  
        # sb.table('favorites').delete().match({
        #     'user_id': user_id,
        #     'clip_id': clip_id
        # }).execute()
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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
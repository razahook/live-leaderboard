import requests
import os
from flask import Blueprint, jsonify, request
from routes.supabase_client import get_supabase

medal_clips_bp = Blueprint('medal_clips', __name__)

def _resolve_streamer_id(supabase_client, medal_username: str):
    """Find or create a streamer row and return its id. Best-effort; returns None on failure."""
    try:
        if supabase_client is None or not medal_username:
            return None
        username = medal_username.lower()
        res = supabase_client.table('streamers').select('id').eq('medal_username', username).limit(1).execute()
        if res.data:
            return res.data[0]['id']
        # Create minimal row for Medal.tv user
        ins = supabase_client.table('streamers').insert({
            'medal_username': username,
            'apex_names': [],
            'twitch_login': None,
            'twitch_display_name': None,
            'twitch_id': None,
            'country_code': None,
            'profile_image_url': None
        }).execute()
        if ins.data:
            return ins.data[0]['id']
    except Exception as e:
        print(f"Medal streamer resolve failed for {medal_username}: {e}")
    return None

def _save_medal_clip_metadata(clip_data: dict, username: str):
    """Save Medal.tv clip metadata to database"""
    try:
        sb = get_supabase()
        if sb is not None:
            try:
                streamer_id = _resolve_streamer_id(sb, username)
                payload = {
                    'source': 'medal',
                    'external_id': clip_data['external_id'],
                    'url': clip_data['url'],
                    'embed_url': clip_data['embed_url'],
                    'edit_url': clip_data['url'],  # Medal doesn't have separate edit URLs
                    'broadcaster_login': username.lower(),
                    'streamer_id': streamer_id,
                    'creator_login': username,
                    'created_by_user_id': None,  # Would need auth context
                    'title': clip_data['title'],
                    'duration': clip_data['duration'],
                    'view_count': clip_data['view_count'],
                    'thumbnail_url': clip_data.get('thumbnail_url'),
                    'extra': clip_data  # Use dict directly for JSONB
                }
                
                # Check if clip already exists
                existing = sb.table('clips').select('id').eq('external_id', clip_data['external_id']).limit(1).execute()
                if not existing.data:
                    sb.table('clips').insert(payload).execute()
                    print(f"Saved Medal clip: {clip_data['external_id']}")
                else:
                    print(f"Medal clip already exists: {clip_data['external_id']}")
            except Exception as e:
                print(f"Failed to save Medal clip to Supabase: {e}")
    except Exception as e:
        print(f"Medal clip save failed: {e}")

def _get_edge_config():
    """Get Edge Config settings for Medal.tv"""
    try:
        url = os.environ.get('EDGE_CONFIG')
        if url:
            response = requests.get(url, timeout=3)
            if response.ok:
                return response.json()
    except:
        pass
    # Fallback config
    return {
        'medal_config': {
            'default_category': '5FsRVgww4b',
            'filter_apex_only': True,
            'allow_user_imports': True,
            'max_clips_per_search': 20
        }
    }

@medal_clips_bp.route('/medal-clips/<username>', methods=['GET'])
def get_medal_clips(username):
    """Get clips from Medal.tv for a streamer"""
    try:
        # Get Edge Config settings
        edge_config = _get_edge_config()
        medal_config = edge_config.get('medal_config', {})
        
        medal_api_key = os.environ.get('MEDAL_API_KEY', 'priv_MlSdfkC3DlcNgudEhJUonZarbRNjZzh8')
        if not medal_api_key:
            return jsonify({
                "success": True,
                "data": {
                    "clips": [],
                    "count": 0,
                    "source": "medal",
                    "message": f"Medal.tv API key not configured - please add MEDAL_API_KEY environment variable to Vercel"
                }
            })
        
        # Medal.tv API headers as per documentation
        headers = {
            'Authorization': medal_api_key,  # No 'Bearer ' prefix needed
            'Content-Type': 'application/json'
        }
        
        # Use Edge Config for category filtering
        default_category = medal_config.get('default_category', '5FsRVgww4b')
        filter_apex_only = medal_config.get('filter_apex_only', True)
        max_clips = medal_config.get('max_clips_per_search', 20)
        
        # Get categoryId from request args or use Edge Config default
        category_id = request.args.get('categoryId', default_category if filter_apex_only else None)
        
        # Build search URL with Edge Config settings
        search_url = f'https://developers.medal.tv/v1/search?text={username}&limit={max_clips}'
        if category_id:
            search_url += f'&categoryId={category_id}'
        search_response = requests.get(search_url, headers=headers, timeout=10)
        
        if search_response.status_code == 200:
            search_data = search_response.json()
            content_objects = search_data.get('contentObjects', [])
            
            if not content_objects:
                return jsonify({
                    "success": True,
                    "data": {
                        "clips": [],
                        "count": 0,
                        "source": "medal",
                        "message": f"No Medal.tv clips found for {username}"
                    }
                })
            
            # Transform Medal clips to match our format using the documented response structure
            transformed_clips = []
            for clip in content_objects:
                # Extract user info from credits field
                credits = clip.get('credits', '')
                medal_user_id = None
                if 'medal.tv/users/' in credits:
                    medal_user_id = credits.split('medal.tv/users/')[-1].split(')')[0]
                
                transformed_clip = {
                    'external_id': f"medal_{clip.get('contentId', '').replace('cid', '')}",
                    'source': 'medal',
                    'url': clip.get('directClipUrl', ''),
                    'embed_url': clip.get('embedIframeUrl', ''),
                    'title': clip.get('contentTitle', 'Untitled'),
                    'duration': clip.get('videoLengthSeconds', 0),
                    'view_count': clip.get('contentViews', 0),
                    'thumbnail_url': None,  # Medal.tv doesn't provide thumbnails in basic API
                    'created_at': clip.get('createdTimestamp'),
                    'broadcaster_login': username.lower(),
                    'medal_user_id': medal_user_id,
                    'category_id': clip.get('categoryId'),
                    'likes': clip.get('contentLikes', 0)
                }
                
                transformed_clips.append(transformed_clip)
                
                # Save clip to database
                _save_medal_clip_metadata(transformed_clip, username)
            
            return jsonify({
                "success": True,
                "data": {
                    "clips": transformed_clips,
                    "count": len(transformed_clips),
                    "source": "medal",
                    "message": f"Found {len(transformed_clips)} Medal.tv clips for {username}"
                }
            })
        else:
            return jsonify({"success": False, "error": f"Medal search API error: {search_response.status_code}"}), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@medal_clips_bp.route('/medal-clips/trending/<game_name>', methods=['GET'])
def get_medal_trending_clips(game_name):
    """Get trending Medal.tv clips for a specific game"""
    try:
        medal_api_key = os.environ.get('MEDAL_API_KEY', 'priv_MlSdfkC3DlcNgudEhJUonZarbRNjZzh8')
        
        # Medal.tv API headers as per documentation
        headers = {
            'Authorization': medal_api_key,
            'Content-Type': 'application/json'
        }
        
        # Search for trending clips by game name
        search_url = f'https://developers.medal.tv/v1/search?text={game_name}&limit=20'
        search_response = requests.get(search_url, headers=headers, timeout=10)
        
        if search_response.status_code == 200:
            search_data = search_response.json()
            content_objects = search_data.get('contentObjects', [])
            
            if not content_objects:
                return jsonify({
                    "success": True,
                    "data": {
                        "clips": [],
                        "count": 0,
                        "source": "medal",
                        "message": f"No trending Medal.tv clips found for {game_name}"
                    }
                })
            
            # Transform Medal clips to match our format
            transformed_clips = []
            for clip in content_objects:
                # Extract user info from credits field
                credits = clip.get('credits', '')
                medal_user_id = None
                if 'medal.tv/users/' in credits:
                    medal_user_id = credits.split('medal.tv/users/')[-1].split(')')[0]
                
                transformed_clips.append({
                    'external_id': f"medal_{clip.get('contentId', '').replace('cid', '')}",
                    'source': 'medal',
                    'url': clip.get('directClipUrl', ''),
                    'embed_url': clip.get('embedIframeUrl', ''),
                    'title': clip.get('contentTitle', 'Untitled'),
                    'duration': clip.get('videoLengthSeconds', 0),
                    'view_count': clip.get('contentViews', 0),
                    'thumbnail_url': None,
                    'created_at': clip.get('createdTimestamp'),
                    'broadcaster_login': medal_user_id or 'unknown',
                    'medal_user_id': medal_user_id,
                    'category_id': clip.get('categoryId'),
                    'likes': clip.get('contentLikes', 0),
                    'game': game_name
                })
            
            return jsonify({
                "success": True,
                "data": {
                    "clips": transformed_clips,
                    "count": len(transformed_clips),
                    "source": "medal",
                    "game": game_name,
                    "message": f"Found {len(transformed_clips)} trending Medal.tv clips for {game_name}"
                }
            })
        else:
            return jsonify({"success": False, "error": f"Medal trending API error: {search_response.status_code}"}), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@medal_clips_bp.route('/medal-clips/categories', methods=['GET'])
def get_medal_categories():
    """Get list of Medal.tv game categories"""
    try:
        medal_api_key = os.environ.get('MEDAL_API_KEY', 'priv_MlSdfkC3DlcNgudEhJUonZarbRNjZzh8')
        
        headers = {
            'Authorization': medal_api_key,
            'Content-Type': 'application/json'
        }
        
        categories_url = 'https://developers.medal.tv/v1/categories'
        response = requests.get(categories_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            categories_data = response.json()
            return jsonify({
                "success": True,
                "data": categories_data
            })
        else:
            return jsonify({"success": False, "error": f"Medal categories API error: {response.status_code}"}), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@medal_clips_bp.route('/import-medal-clip', methods=['POST'])
def import_medal_clip():
    """Import a specific Medal.tv clip by URL and link to streamer"""
    try:
        # Check if user imports are allowed via Edge Config
        edge_config = _get_edge_config()
        medal_config = edge_config.get('medal_config', {})
        
        if not medal_config.get('allow_user_imports', True):
            return jsonify({
                "success": False,
                "error": "User clip imports are currently disabled"
            }), 403
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        medal_url = data.get('medal_url')
        streamer_name = data.get('streamer_name')  # Which streamer to link this to
        
        if not medal_url or not streamer_name:
            return jsonify({
                "success": False, 
                "error": "Both 'medal_url' and 'streamer_name' are required"
            }), 400
        
        # Extract clip ID from Medal.tv URL
        import re
        clip_match = re.search(r'medal\.tv/clip/([a-zA-Z0-9]+)', medal_url)
        if not clip_match:
            return jsonify({
                "success": False,
                "error": "Invalid Medal.tv URL format"
            }), 400
        
        clip_id = clip_match.group(1)
        medal_api_key = os.environ.get('MEDAL_API_KEY', 'priv_MlSdfkC3DlcNgudEhJUonZarbRNjZzh8')
        
        headers = {
            'Authorization': medal_api_key,
            'Content-Type': 'application/json'
        }
        
        # Get clip details from Medal.tv API
        clip_url = f'https://developers.medal.tv/v1/clips/{clip_id}'
        response = requests.get(clip_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            clip_data = response.json()
            
            # Transform to our format
            transformed_clip = {
                'external_id': f"medal_{clip_id}",
                'source': 'medal',
                'url': medal_url,
                'embed_url': clip_data.get('embedIframeUrl', ''),
                'title': clip_data.get('contentTitle', 'Imported Medal.tv Clip'),
                'duration': clip_data.get('videoLengthSeconds', 0),
                'view_count': clip_data.get('contentViews', 0),
                'thumbnail_url': None,
                'created_at': clip_data.get('createdTimestamp'),
                'broadcaster_login': streamer_name.lower(),
                'medal_user_id': None,
                'category_id': clip_data.get('categoryId'),
                'likes': clip_data.get('contentLikes', 0),
                'imported_by_user': True  # Mark as user-imported
            }
            
            # Save to database with custom streamer linking
            _save_medal_clip_metadata(transformed_clip, streamer_name)
            
            return jsonify({
                "success": True,
                "data": {
                    "clip": transformed_clip,
                    "message": f"Successfully imported Medal.tv clip and linked to {streamer_name}",
                    "linked_to": streamer_name
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": f"Could not fetch clip from Medal.tv API: {response.status_code}"
            }), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@medal_clips_bp.route('/link-clip-to-streamer', methods=['POST'])
def link_clip_to_streamer():
    """Link an existing clip to a different streamer"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        clip_external_id = data.get('clip_id')
        new_streamer_name = data.get('streamer_name')
        
        if not clip_external_id or not new_streamer_name:
            return jsonify({
                "success": False,
                "error": "Both 'clip_id' and 'streamer_name' are required"
            }), 400
        
        sb = get_supabase()
        if sb is None:
            return jsonify({"success": False, "error": "Database not available"}), 500
        
        # Find new streamer
        new_streamer_id = _resolve_streamer_id(sb, new_streamer_name)
        
        # Update clip to link to new streamer
        result = sb.table('clips').update({
            'streamer_id': new_streamer_id,
            'broadcaster_login': new_streamer_name.lower()
        }).eq('external_id', clip_external_id).execute()
        
        if result.data:
            return jsonify({
                "success": True,
                "message": f"Clip {clip_external_id} successfully linked to {new_streamer_name}",
                "data": result.data[0]
            })
        else:
            return jsonify({
                "success": False,
                "error": "Clip not found or update failed"
            }), 404
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
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
            'twitch_login': None
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
                    'title': clip_data['title'],
                    'duration': clip_data['duration'],
                    'view_count': clip_data['view_count'],
                    'thumbnail_url': clip_data['thumbnail_url'],
                    'extra': str(clip_data)
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

@medal_clips_bp.route('/medal-clips/<username>', methods=['GET'])
def get_medal_clips(username):
    """Get clips from Medal.tv for a streamer"""
    try:
        medal_api_key = os.environ.get('MEDAL_API_KEY')
        if not medal_api_key:
            return jsonify({"success": False, "error": "Medal.tv API not configured"}), 500
        
        # Medal.tv API headers as per documentation
        headers = {
            'Authorization': medal_api_key,  # No 'Bearer ' prefix needed
            'Content-Type': 'application/json'
        }
        
        # Search for clips by username using the search endpoint
        search_url = f'https://developers.medal.tv/v1/search?text={username}&limit=20'
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
        medal_api_key = os.environ.get('MEDAL_API_KEY')
        if not medal_api_key:
            return jsonify({"success": False, "error": "Medal.tv API not configured"}), 500
        
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
        medal_api_key = os.environ.get('MEDAL_API_KEY')
        if not medal_api_key:
            return jsonify({"success": False, "error": "Medal.tv API not configured"}), 500
        
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
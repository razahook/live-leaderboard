import requests
import json
import time
import os
from flask import Blueprint, jsonify, request
from routes.twitch_integration import get_twitch_access_token

twitch_live_rewind_bp = Blueprint('twitch_live_rewind', __name__)

# ==========================================
# OFFICIAL TWITCH CLIPS API IMPLEMENTATION
# ==========================================

@twitch_live_rewind_bp.route('/stream-live-streamers', methods=['GET'])
def get_live_streamers():
    """Get currently live streamers using Twitch API"""
    try:
        access_token = get_twitch_access_token()
        if not access_token:
            return jsonify({
                'success': False,
                'error': 'Failed to get Twitch access token'
            }), 500
            
        client_id = os.environ.get('TWITCH_CLIENT_ID')
        if not client_id:
            return jsonify({
                'success': False,
                'error': 'TWITCH_CLIENT_ID not configured'
            }), 500
            
        headers = {
            'Client-Id': client_id,
            'Authorization': f'Bearer {access_token}'
        }
        
        # Get top live streams
        streams_response = requests.get(
            'https://api.twitch.tv/helix/streams?first=20&language=en', 
            headers=headers, 
            timeout=10
        )
        
        if streams_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': f'Failed to get live streams: {streams_response.status_code}'
            }), 500
            
        streams_data = streams_response.json().get('data', [])
        
        live_streamers = []
        for stream in streams_data:
            # Clean title of emojis that cause encoding issues
            title = stream['title']
            # Remove common problematic characters
            title = title.encode('ascii', 'ignore').decode('ascii')
            
            # Also clean display name and game name
            display_name = stream['user_name'].encode('ascii', 'ignore').decode('ascii')
            game_name = stream['game_name'].encode('ascii', 'ignore').decode('ascii')
            
            live_streamers.append({
                'login': stream['user_login'],
                'display_name': display_name,
                'title': title,
                'game_name': game_name,
                'viewer_count': stream['viewer_count'],
                'language': stream['language'],
                'thumbnail_url': stream['thumbnail_url']
            })
            
        return jsonify({
            'success': True,
            'streamers': live_streamers,
            'count': len(live_streamers),
            'message': f'Found {len(live_streamers)} live streamers'
        })
        
    except Exception as e:
        print(f"Error getting live streamers: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Removed - This route used deprecated PlaybackAccessToken GraphQL which causes server errors
# Use official Twitch embeds and Clips API instead

@twitch_live_rewind_bp.route('/stream-clips/create/<channel_login>', methods=['POST'])
def create_clip_official_api(channel_login):
    """Create a clip using official Twitch Clips API"""
    try:
        # Get Twitch access token
        access_token = get_twitch_access_token()
        if not access_token:
            return jsonify({
                'success': False,
                'error': 'Failed to get Twitch access token'
            }), 500
            
        client_id = os.environ.get('TWITCH_CLIENT_ID')
        if not client_id:
            return jsonify({
                'success': False,
                'error': 'TWITCH_CLIENT_ID not configured'
            }), 500
            
        headers = {
            'Client-Id': client_id,
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Get broadcaster ID first
        user_response = requests.get(
            f"https://api.twitch.tv/helix/users?login={channel_login}", 
            headers=headers, 
            timeout=10
        )
        
        if user_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': 'Failed to get user info'
            }), 500
            
        user_data = user_response.json().get('data', [])
        if not user_data:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
            
        broadcaster_id = user_data[0]['id']
        
        # Check if stream is live
        stream_response = requests.get(
            f"https://api.twitch.tv/helix/streams?user_id={broadcaster_id}", 
            headers=headers, 
            timeout=10
        )
        
        if stream_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': 'Failed to get stream info'
            }), 500
            
        stream_data = stream_response.json().get('data', [])
        if not stream_data:
            return jsonify({
                'success': False,
                'error': f'{channel_login} is not currently live'
            }), 404
            
        # Create clip using official API
        clip_data = {
            'broadcaster_id': broadcaster_id,
            'has_delay': False  # Set to True if broadcaster has delay enabled
        }
        
        # Add optional parameters from request
        request_data = request.get_json() or {}
        if 'started_at' in request_data:
            clip_data['started_at'] = request_data['started_at']
        if 'ended_at' in request_data:
            clip_data['ended_at'] = request_data['ended_at']
            
        clip_response = requests.post(
            'https://api.twitch.tv/helix/clips',
            headers=headers,
            json=clip_data,
            timeout=15
        )
        
        if clip_response.status_code != 202:  # Twitch returns 202 for clip creation
            return jsonify({
                'success': False,
                'error': f'Failed to create clip: {clip_response.status_code}',
                'details': clip_response.text
            }), clip_response.status_code
            
        clip_result = clip_response.json()
        clip_info = clip_result.get('data', [{}])[0]
        
        # Wait a moment for clip to be processed
        time.sleep(2)
        
        # Get clip details
        clip_id = clip_info.get('id')
        edit_url = clip_info.get('edit_url')
        
        if clip_id:
            # Get full clip information
            clip_details_response = requests.get(
                f"https://api.twitch.tv/helix/clips?id={clip_id}",
                headers=headers,
                timeout=10
            )
            
            if clip_details_response.status_code == 200:
                clip_details = clip_details_response.json().get('data', [{}])[0]
                
                return jsonify({
                    'success': True,
                    'data': {
                        'clip_id': clip_id,
                        'url': clip_details.get('url', f'https://clips.twitch.tv/{clip_id}'),
                        'embed_url': clip_details.get('embed_url', f'https://clips.twitch.tv/embed?clip={clip_id}'),
                        'edit_url': edit_url,
                        'broadcaster_name': clip_details.get('broadcaster_name', channel_login),
                        'broadcaster_id': broadcaster_id,
                        'title': clip_details.get('title', 'Untitled Clip'),
                        'view_count': clip_details.get('view_count', 0),
                        'created_at': clip_details.get('created_at'),
                        'thumbnail_url': clip_details.get('thumbnail_url'),
                        'duration': clip_details.get('duration', 30)
                    },
                    'message': 'Clip created successfully!'
                })
        
        # Fallback if we can't get detailed info
        return jsonify({
            'success': True,
            'data': {
                'clip_id': clip_id,
                'edit_url': edit_url,
                'url': f'https://clips.twitch.tv/{clip_id}' if clip_id else None,
                'broadcaster_name': channel_login,
                'broadcaster_id': broadcaster_id
            },
            'message': 'Clip created! Details may take a moment to load.'
        })
        
    except Exception as e:
        print(f"Error creating clip: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_live_rewind_bp.route('/stream-clips/create/<channel_login>', methods=['POST'])
def create_clip_official_api(channel_login):
    """Create a clip using official Twitch Clips API"""
    try:
        # Get Twitch access token
        access_token = get_twitch_access_token()
        if not access_token:
            return jsonify({
                'success': False,
                'error': 'Failed to get Twitch access token'
            }), 500
            
        client_id = os.environ.get('TWITCH_CLIENT_ID')
        if not client_id:
            return jsonify({
                'success': False,
                'error': 'TWITCH_CLIENT_ID not configured'
            }), 500
            
        headers = {
            'Client-Id': client_id,
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Get broadcaster ID first
        user_response = requests.get(
            f"https://api.twitch.tv/helix/users?login={channel_login}", 
            headers=headers, 
            timeout=10
        )
        
        if user_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': 'Failed to get user info'
            }), 500
            
        user_data = user_response.json().get('data', [])
        if not user_data:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
            
        broadcaster_id = user_data[0]['id']
        
        # Check if stream is live
        stream_response = requests.get(
            f"https://api.twitch.tv/helix/streams?user_id={broadcaster_id}", 
            headers=headers, 
            timeout=10
        )
        
        if stream_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': 'Failed to get stream info'
            }), 500
            
        stream_data = stream_response.json().get('data', [])
        if not stream_data:
            return jsonify({
                'success': False,
                'error': f'{channel_login} is not currently live'
            }), 404
            
        # Create clip using official API
        clip_data = {
            'broadcaster_id': broadcaster_id,
            'has_delay': False  # Set to True if broadcaster has delay enabled
        }
        
        # Add optional parameters from request
        request_data = request.get_json() or {}
        if 'started_at' in request_data:
            clip_data['started_at'] = request_data['started_at']
        if 'ended_at' in request_data:
            clip_data['ended_at'] = request_data['ended_at']
            
        clip_response = requests.post(
            'https://api.twitch.tv/helix/clips',
            headers=headers,
            json=clip_data,
            timeout=15
        )
        
        if clip_response.status_code != 202:  # Twitch returns 202 for clip creation
            return jsonify({
                'success': False,
                'error': f'Failed to create clip: {clip_response.status_code}',
                'details': clip_response.text
            }), clip_response.status_code
            
        clip_result = clip_response.json()
        clip_info = clip_result.get('data', [{}])[0]
        
        # Wait a moment for clip to be processed
        time.sleep(2)
        
        # Get clip details
        clip_id = clip_info.get('id')
        edit_url = clip_info.get('edit_url')
        
        if clip_id:
            # Get full clip information
            clip_details_response = requests.get(
                f"https://api.twitch.tv/helix/clips?id={clip_id}",
                headers=headers,
                timeout=10
            )
            
            if clip_details_response.status_code == 200:
                clip_details = clip_details_response.json().get('data', [{}])[0]
                
                return jsonify({
                    'success': True,
                    'data': {
                        'clip_id': clip_id,
                        'url': clip_details.get('url', f'https://clips.twitch.tv/{clip_id}'),
                        'embed_url': clip_details.get('embed_url', f'https://clips.twitch.tv/embed?clip={clip_id}'),
                        'edit_url': edit_url,
                        'broadcaster_name': clip_details.get('broadcaster_name', channel_login),
                        'broadcaster_id': broadcaster_id,
                        'title': clip_details.get('title', 'Untitled Clip'),
                        'view_count': clip_details.get('view_count', 0),
                        'created_at': clip_details.get('created_at'),
                        'thumbnail_url': clip_details.get('thumbnail_url'),
                        'duration': clip_details.get('duration', 30)
                    },
                    'message': 'Clip created successfully!'
                })
        
        # Fallback if we can't get detailed info
        return jsonify({
            'success': True,
            'data': {
                'clip_id': clip_id,
                'edit_url': edit_url,
                'url': f'https://clips.twitch.tv/{clip_id}' if clip_id else None,
                'broadcaster_name': channel_login,
                'broadcaster_id': broadcaster_id
            },
            'message': 'Clip created! Details may take a moment to load.'
        })
        
    except Exception as e:
        print(f"Error creating clip: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_live_rewind_bp.route('/stream-clips/create/<channel_login>', methods=['POST'])
def create_clip_official_api(channel_login):
    """Create a clip using official Twitch Clips API"""
    try:
        # Get Twitch access token
        access_token = get_twitch_access_token()
        if not access_token:
            return jsonify({
                'success': False,
                'error': 'Failed to get Twitch access token'
            }), 500
            
        client_id = os.environ.get('TWITCH_CLIENT_ID')
        if not client_id:
            return jsonify({
                'success': False,
                'error': 'TWITCH_CLIENT_ID not configured'
            }), 500
            
        headers = {
            'Client-Id': client_id,
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Get broadcaster ID first
        user_response = requests.get(
            f"https://api.twitch.tv/helix/users?login={channel_login}", 
            headers=headers, 
            timeout=10
        )
        
        if user_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': 'Failed to get user info'
            }), 500
            
        user_data = user_response.json().get('data', [])
        if not user_data:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
            
        broadcaster_id = user_data[0]['id']
        
        # Check if stream is live
        stream_response = requests.get(
            f"https://api.twitch.tv/helix/streams?user_id={broadcaster_id}", 
            headers=headers, 
            timeout=10
        )
        
        if stream_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': 'Failed to get stream info'
            }), 500
            
        stream_data = stream_response.json().get('data', [])
        if not stream_data:
            return jsonify({
                'success': False,
                'error': f'{channel_login} is not currently live'
            }), 404
            
        # Create clip using official API
        clip_data = {
            'broadcaster_id': broadcaster_id,
            'has_delay': False  # Set to True if broadcaster has delay enabled
        }
        
        # Add optional parameters from request
        request_data = request.get_json() or {}
        if 'started_at' in request_data:
            clip_data['started_at'] = request_data['started_at']
        if 'ended_at' in request_data:
            clip_data['ended_at'] = request_data['ended_at']
            
        clip_response = requests.post(
            'https://api.twitch.tv/helix/clips',
            headers=headers,
            json=clip_data,
            timeout=15
        )
        
        if clip_response.status_code != 202:  # Twitch returns 202 for clip creation
            return jsonify({
                'success': False,
                'error': f'Failed to create clip: {clip_response.status_code}',
                'details': clip_response.text
            }), clip_response.status_code
            
        clip_result = clip_response.json()
        clip_info = clip_result.get('data', [{}])[0]
        
        # Wait a moment for clip to be processed
        time.sleep(2)
        
        # Get clip details
        clip_id = clip_info.get('id')
        edit_url = clip_info.get('edit_url')
        
        if clip_id:
            # Get full clip information
            clip_details_response = requests.get(
                f"https://api.twitch.tv/helix/clips?id={clip_id}",
                headers=headers,
                timeout=10
            )
            
            if clip_details_response.status_code == 200:
                clip_details = clip_details_response.json().get('data', [{}])[0]
                
                return jsonify({
                    'success': True,
                    'data': {
                        'clip_id': clip_id,
                        'url': clip_details.get('url', f'https://clips.twitch.tv/{clip_id}'),
                        'embed_url': clip_details.get('embed_url', f'https://clips.twitch.tv/embed?clip={clip_id}'),
                        'edit_url': edit_url,
                        'broadcaster_name': clip_details.get('broadcaster_name', channel_login),
                        'broadcaster_id': broadcaster_id,
                        'title': clip_details.get('title', 'Untitled Clip'),
                        'view_count': clip_details.get('view_count', 0),
                        'created_at': clip_details.get('created_at'),
                        'thumbnail_url': clip_details.get('thumbnail_url'),
                        'duration': clip_details.get('duration', 30)
                    },
                    'message': 'Clip created successfully!'
                })
        
        # Fallback if we can't get detailed info
        return jsonify({
            'success': True,
            'data': {
                'clip_id': clip_id,
                'edit_url': edit_url,
                'url': f'https://clips.twitch.tv/{clip_id}' if clip_id else None,
                'broadcaster_name': channel_login,
                'broadcaster_id': broadcaster_id
            },
            'message': 'Clip created! Details may take a moment to load.'
        })
        
    except Exception as e:
        print(f"Error creating clip: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
# Use official Twitch Clips API instead

@twitch_live_rewind_bp.route('/stream-clips/create/<channel_login>', methods=['POST'])
def create_clip_official_api(channel_login):
    """Create a clip using official Twitch Clips API"""
    try:
        # Get Twitch access token
        access_token = get_twitch_access_token()
        if not access_token:
            return jsonify({
                'success': False,
                'error': 'Failed to get Twitch access token'
            }), 500
            
        client_id = os.environ.get('TWITCH_CLIENT_ID')
        if not client_id:
            return jsonify({
                'success': False,
                'error': 'TWITCH_CLIENT_ID not configured'
            }), 500
            
        headers = {
            'Client-Id': client_id,
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Get broadcaster ID first
        user_response = requests.get(
            f"https://api.twitch.tv/helix/users?login={channel_login}", 
            headers=headers, 
            timeout=10
        )
        
        if user_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': 'Failed to get user info'
            }), 500
            
        user_data = user_response.json().get('data', [])
        if not user_data:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
            
        broadcaster_id = user_data[0]['id']
        
        # Check if stream is live
        stream_response = requests.get(
            f"https://api.twitch.tv/helix/streams?user_id={broadcaster_id}", 
            headers=headers, 
            timeout=10
        )
        
        if stream_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': 'Failed to get stream info'
            }), 500
            
        stream_data = stream_response.json().get('data', [])
        if not stream_data:
            return jsonify({
                'success': False,
                'error': f'{channel_login} is not currently live'
            }), 404
            
        # Create clip using official API
        clip_data = {
            'broadcaster_id': broadcaster_id,
            'has_delay': False  # Set to True if broadcaster has delay enabled
        }
        
        # Add optional parameters from request
        request_data = request.get_json() or {}
        if 'started_at' in request_data:
            clip_data['started_at'] = request_data['started_at']
        if 'ended_at' in request_data:
            clip_data['ended_at'] = request_data['ended_at']
            
        clip_response = requests.post(
            'https://api.twitch.tv/helix/clips',
            headers=headers,
            json=clip_data,
            timeout=15
        )
        
        if clip_response.status_code != 202:  # Twitch returns 202 for clip creation
            return jsonify({
                'success': False,
                'error': f'Failed to create clip: {clip_response.status_code}',
                'details': clip_response.text
            }), clip_response.status_code
            
        clip_result = clip_response.json()
        clip_info = clip_result.get('data', [{}])[0]
        
        # Wait a moment for clip to be processed
        time.sleep(2)
        
        # Get clip details
        clip_id = clip_info.get('id')
        edit_url = clip_info.get('edit_url')
        
        if clip_id:
            # Get full clip information
            clip_details_response = requests.get(
                f"https://api.twitch.tv/helix/clips?id={clip_id}",
                headers=headers,
                timeout=10
            )
            
            if clip_details_response.status_code == 200:
                clip_details = clip_details_response.json().get('data', [{}])[0]
                
                return jsonify({
                    'success': True,
                    'data': {
                        'clip_id': clip_id,
                        'url': clip_details.get('url', f'https://clips.twitch.tv/{clip_id}'),
                        'embed_url': clip_details.get('embed_url', f'https://clips.twitch.tv/embed?clip={clip_id}'),
                        'edit_url': edit_url,
                        'broadcaster_name': clip_details.get('broadcaster_name', channel_login),
                        'broadcaster_id': broadcaster_id,
                        'title': clip_details.get('title', 'Untitled Clip'),
                        'view_count': clip_details.get('view_count', 0),
                        'created_at': clip_details.get('created_at'),
                        'thumbnail_url': clip_details.get('thumbnail_url'),
                        'duration': clip_details.get('duration', 30)
                    },
                    'message': 'Clip created successfully!'
                })
        
        # Fallback if we can't get detailed info
        return jsonify({
            'success': True,
            'data': {
                'clip_id': clip_id,
                'edit_url': edit_url,
                'url': f'https://clips.twitch.tv/{clip_id}' if clip_id else None,
                'broadcaster_name': channel_login,
                'broadcaster_id': broadcaster_id
            },
            'message': 'Clip created! Details may take a moment to load.'
        })
        
    except Exception as e:
        print(f"Error creating clip: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_live_rewind_bp.route('/stream-clips/create/<channel_login>', methods=['POST'])
def create_clip_official_api(channel_login):
    """Create a clip using official Twitch Clips API"""
    try:
        # Get Twitch access token
        access_token = get_twitch_access_token()
        if not access_token:
            return jsonify({
                'success': False,
                'error': 'Failed to get Twitch access token'
            }), 500
            
        client_id = os.environ.get('TWITCH_CLIENT_ID')
        if not client_id:
            return jsonify({
                'success': False,
                'error': 'TWITCH_CLIENT_ID not configured'
            }), 500
            
        headers = {
            'Client-Id': client_id,
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Get broadcaster ID first
        user_response = requests.get(
            f"https://api.twitch.tv/helix/users?login={channel_login}", 
            headers=headers, 
            timeout=10
        )
        
        if user_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': 'Failed to get user info'
            }), 500
            
        user_data = user_response.json().get('data', [])
        if not user_data:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
            
        broadcaster_id = user_data[0]['id']
        
        # Check if stream is live
        stream_response = requests.get(
            f"https://api.twitch.tv/helix/streams?user_id={broadcaster_id}", 
            headers=headers, 
            timeout=10
        )
        
        if stream_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': 'Failed to get stream info'
            }), 500
            
        stream_data = stream_response.json().get('data', [])
        if not stream_data:
            return jsonify({
                'success': False,
                'error': f'{channel_login} is not currently live'
            }), 404
            
        # Create clip using official API
        clip_data = {
            'broadcaster_id': broadcaster_id,
            'has_delay': False  # Set to True if broadcaster has delay enabled
        }
        
        # Add optional parameters from request
        request_data = request.get_json() or {}
        if 'started_at' in request_data:
            clip_data['started_at'] = request_data['started_at']
        if 'ended_at' in request_data:
            clip_data['ended_at'] = request_data['ended_at']
            
        clip_response = requests.post(
            'https://api.twitch.tv/helix/clips',
            headers=headers,
            json=clip_data,
            timeout=15
        )
        
        if clip_response.status_code != 202:  # Twitch returns 202 for clip creation
            return jsonify({
                'success': False,
                'error': f'Failed to create clip: {clip_response.status_code}',
                'details': clip_response.text
            }), clip_response.status_code
            
        clip_result = clip_response.json()
        clip_info = clip_result.get('data', [{}])[0]
        
        # Wait a moment for clip to be processed
        time.sleep(2)
        
        # Get clip details
        clip_id = clip_info.get('id')
        edit_url = clip_info.get('edit_url')
        
        if clip_id:
            # Get full clip information
            clip_details_response = requests.get(
                f"https://api.twitch.tv/helix/clips?id={clip_id}",
                headers=headers,
                timeout=10
            )
            
            if clip_details_response.status_code == 200:
                clip_details = clip_details_response.json().get('data', [{}])[0]
                
                return jsonify({
                    'success': True,
                    'data': {
                        'clip_id': clip_id,
                        'url': clip_details.get('url', f'https://clips.twitch.tv/{clip_id}'),
                        'embed_url': clip_details.get('embed_url', f'https://clips.twitch.tv/embed?clip={clip_id}'),
                        'edit_url': edit_url,
                        'broadcaster_name': clip_details.get('broadcaster_name', channel_login),
                        'broadcaster_id': broadcaster_id,
                        'title': clip_details.get('title', 'Untitled Clip'),
                        'view_count': clip_details.get('view_count', 0),
                        'created_at': clip_details.get('created_at'),
                        'thumbnail_url': clip_details.get('thumbnail_url'),
                        'duration': clip_details.get('duration', 30)
                    },
                    'message': 'Clip created successfully!'
                })
        
        # Fallback if we can't get detailed info
        return jsonify({
            'success': True,
            'data': {
                'clip_id': clip_id,
                'edit_url': edit_url,
                'url': f'https://clips.twitch.tv/{clip_id}' if clip_id else None,
                'broadcaster_name': channel_login,
                'broadcaster_id': broadcaster_id
            },
            'message': 'Clip created! Details may take a moment to load.'
        })
        
    except Exception as e:
        print(f"Error creating clip: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_live_rewind_bp.route('/stream-clips/create/<channel_login>', methods=['POST'])
def create_clip_official_api(channel_login):
    """Create a clip using official Twitch Clips API"""
    try:
        # Get Twitch access token
        access_token = get_twitch_access_token()
        if not access_token:
            return jsonify({
                'success': False,
                'error': 'Failed to get Twitch access token'
            }), 500
            
        client_id = os.environ.get('TWITCH_CLIENT_ID')
        if not client_id:
            return jsonify({
                'success': False,
                'error': 'TWITCH_CLIENT_ID not configured'
            }), 500
            
        headers = {
            'Client-Id': client_id,
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Get broadcaster ID first
        user_response = requests.get(
            f"https://api.twitch.tv/helix/users?login={channel_login}", 
            headers=headers, 
            timeout=10
        )
        
        if user_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': 'Failed to get user info'
            }), 500
            
        user_data = user_response.json().get('data', [])
        if not user_data:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
            
        broadcaster_id = user_data[0]['id']
        
        # Check if stream is live
        stream_response = requests.get(
            f"https://api.twitch.tv/helix/streams?user_id={broadcaster_id}", 
            headers=headers, 
            timeout=10
        )
        
        if stream_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': 'Failed to get stream info'
            }), 500
            
        stream_data = stream_response.json().get('data', [])
        if not stream_data:
            return jsonify({
                'success': False,
                'error': f'{channel_login} is not currently live'
            }), 404
            
        # Create clip using official API
        clip_data = {
            'broadcaster_id': broadcaster_id,
            'has_delay': False  # Set to True if broadcaster has delay enabled
        }
        
        # Add optional parameters from request
        request_data = request.get_json() or {}
        if 'started_at' in request_data:
            clip_data['started_at'] = request_data['started_at']
        if 'ended_at' in request_data:
            clip_data['ended_at'] = request_data['ended_at']
            
        clip_response = requests.post(
            'https://api.twitch.tv/helix/clips',
            headers=headers,
            json=clip_data,
            timeout=15
        )
        
        if clip_response.status_code != 202:  # Twitch returns 202 for clip creation
            return jsonify({
                'success': False,
                'error': f'Failed to create clip: {clip_response.status_code}',
                'details': clip_response.text
            }), clip_response.status_code
            
        clip_result = clip_response.json()
        clip_info = clip_result.get('data', [{}])[0]
        
        # Wait a moment for clip to be processed
        time.sleep(2)
        
        # Get clip details
        clip_id = clip_info.get('id')
        edit_url = clip_info.get('edit_url')
        
        if clip_id:
            # Get full clip information
            clip_details_response = requests.get(
                f"https://api.twitch.tv/helix/clips?id={clip_id}",
                headers=headers,
                timeout=10
            )
            
            if clip_details_response.status_code == 200:
                clip_details = clip_details_response.json().get('data', [{}])[0]
                
                return jsonify({
                    'success': True,
                    'data': {
                        'clip_id': clip_id,
                        'url': clip_details.get('url', f'https://clips.twitch.tv/{clip_id}'),
                        'embed_url': clip_details.get('embed_url', f'https://clips.twitch.tv/embed?clip={clip_id}'),
                        'edit_url': edit_url,
                        'broadcaster_name': clip_details.get('broadcaster_name', channel_login),
                        'broadcaster_id': broadcaster_id,
                        'title': clip_details.get('title', 'Untitled Clip'),
                        'view_count': clip_details.get('view_count', 0),
                        'created_at': clip_details.get('created_at'),
                        'thumbnail_url': clip_details.get('thumbnail_url'),
                        'duration': clip_details.get('duration', 30)
                    },
                    'message': 'Clip created successfully!'
                })
        
        # Fallback if we can't get detailed info
        return jsonify({
            'success': True,
            'data': {
                'clip_id': clip_id,
                'edit_url': edit_url,
                'url': f'https://clips.twitch.tv/{clip_id}' if clip_id else None,
                'broadcaster_name': channel_login,
                'broadcaster_id': broadcaster_id
            },
            'message': 'Clip created! Details may take a moment to load.'
        })
        
    except Exception as e:
        print(f"Error creating clip: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
from flask import Blueprint, jsonify, request
import os
import requests
from routes.twitch_integration import get_twitch_access_token, get_twitch_live_status_batch, extract_twitch_username

twitch_debug_bp = Blueprint('twitch_debug', __name__)

@twitch_debug_bp.route('/debug/twitch-config', methods=['GET'])
def debug_twitch_config():
    """Debug endpoint to check Twitch configuration"""
    client_id = os.environ.get('TWITCH_CLIENT_ID')
    client_secret = os.environ.get('TWITCH_CLIENT_SECRET')
    
    return jsonify({
        "has_client_id": bool(client_id),
        "client_id_length": len(client_id) if client_id else 0,
        "has_client_secret": bool(client_secret),
        "client_secret_length": len(client_secret) if client_secret else 0,
        "client_id_preview": client_id[:8] + "..." if client_id and len(client_id) > 8 else client_id,
        "environment_vars": list(os.environ.keys())
    })

@twitch_debug_bp.route('/debug/twitch-token', methods=['GET'])
def debug_twitch_token():
    """Test getting Twitch access token"""
    try:
        token = get_twitch_access_token()
        if token:
            # Test the token with a simple API call
            client_id = os.environ.get('TWITCH_CLIENT_ID')
            headers = {
                'Client-ID': client_id,
                'Authorization': f'Bearer {token}'
            }
            
            # Try to get a known Twitch user (twitch's own channel)
            response = requests.get(
                'https://api.twitch.tv/helix/users?login=twitch',
                headers=headers
            )
            
            return jsonify({
                "success": True,
                "token_obtained": True,
                "token_length": len(token),
                "token_preview": token[:10] + "...",
                "test_api_call_status": response.status_code,
                "test_api_response": response.json() if response.status_code == 200 else response.text
            })
        else:
            return jsonify({
                "success": False,
                "token_obtained": False,
                "error": "Could not obtain token"
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })

@twitch_debug_bp.route('/debug/twitch-batch', methods=['GET'])
def debug_twitch_batch():
    """Test batch Twitch status check with known streamers"""
    try:
        # Test with some known large streamers who are often live
        test_usernames = ['xqc', 'summit1g', 'shroud', 'ninja', 'pokimane']
        
        results = get_twitch_live_status_batch(test_usernames, batch_size=5)
        
        return jsonify({
            "success": True,
            "tested_usernames": test_usernames,
            "results": results,
            "total_checked": len(test_usernames),
            "total_results": len(results)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        })

@twitch_debug_bp.route('/debug/test-player', methods=['GET'])
def debug_test_player():
    """Test Twitch integration with a specific player"""
    player_name = request.args.get('player', 'imperialhal')
    twitch_url = request.args.get('url', f'https://twitch.tv/{player_name}')
    
    try:
        # Extract username
        username = extract_twitch_username(twitch_url)
        
        if not username:
            return jsonify({
                "success": False,
                "error": "Could not extract username from URL",
                "url": twitch_url
            })
        
        # Check live status
        results = get_twitch_live_status_batch([username], batch_size=1)
        
        return jsonify({
            "success": True,
            "player": player_name,
            "twitch_url": twitch_url,
            "extracted_username": username,
            "live_status": results.get(username, {}),
            "is_live": results.get(username, {}).get('is_live', False)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })
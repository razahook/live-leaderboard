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
        # Import the optimized batch size
        from routes.twitch_integration import BATCH_SIZE, is_vercel
        
        # Test with some known streamers - smaller set for Vercel
        test_usernames = ['imperialhal', 'aceu', 'shroud'] if is_vercel else ['xqc', 'summit1g', 'shroud', 'ninja', 'pokimane']
        
        results = get_twitch_live_status_batch(test_usernames)
        
        return jsonify({
            "success": True,
            "environment": "vercel" if is_vercel else "local",
            "batch_size": BATCH_SIZE,
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

@twitch_debug_bp.route('/debug/overrides-check', methods=['GET'])
def debug_overrides_check():
    """Debug endpoint to check Twitch overrides file loading"""
    try:
        import os
        from routes.apex_scraper import load_twitch_overrides, OVERRIDE_FILE_PATH
        
        # Check various paths
        current_file = __file__
        current_dir = os.path.dirname(__file__)
        parent_dir = os.path.dirname(current_dir)
        root_dir = os.path.dirname(parent_dir)
        
        # Try multiple possible paths
        paths_to_try = [
            OVERRIDE_FILE_PATH,
            os.path.join(root_dir, 'twitch_overrides.json'),
            os.path.join(parent_dir, 'twitch_overrides.json'),
            os.path.join(current_dir, 'twitch_overrides.json'),
            '/var/task/src/twitch_overrides.json',  # Vercel path
        ]
        
        path_results = []
        for path in paths_to_try:
            exists = os.path.exists(path)
            try:
                if exists:
                    with open(path, 'r') as f:
                        content = f.read()
                        import json
                        data = json.loads(content)
                        path_results.append({
                            "path": path,
                            "exists": True,
                            "entries_count": len(data),
                            "sample_keys": list(data.keys())[:3]
                        })
                else:
                    path_results.append({
                        "path": path,
                        "exists": False,
                        "error": "File not found"
                    })
            except Exception as e:
                path_results.append({
                    "path": path,
                    "exists": exists,
                    "error": str(e)
                })
        
        # Try loading overrides
        try:
            overrides = load_twitch_overrides()
            overrides_loaded = True
            overrides_count = len(overrides)
            sample_overrides = dict(list(overrides.items())[:3]) if overrides else {}
        except Exception as e:
            overrides_loaded = False
            overrides_count = 0
            sample_overrides = {"error": str(e)}
        
        return jsonify({
            "success": True,
            "file_paths": {
                "current_file": current_file,
                "current_dir": current_dir,
                "parent_dir": parent_dir,
                "root_dir": root_dir,
                "configured_path": OVERRIDE_FILE_PATH
            },
            "path_checks": path_results,
            "override_loading": {
                "loaded": overrides_loaded,
                "count": overrides_count,
                "sample": sample_overrides
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        })

@twitch_debug_bp.route('/debug/leaderboard-sample', methods=['GET'])
def debug_leaderboard_sample():
    """Debug endpoint to show sample leaderboard data with Twitch info"""
    try:
        from routes.leaderboard_scraper import scrape_leaderboard
        
        # Get sample data (first 5 players only)
        leaderboard_data = scrape_leaderboard(platform="PC", max_players=5)
        
        if not leaderboard_data or not leaderboard_data.get('players'):
            return jsonify({
                "success": False,
                "error": "No leaderboard data returned",
                "data": leaderboard_data
            })
        
        players_sample = leaderboard_data['players'][:3]  # First 3 players only
        
        # Extract relevant debug info
        debug_players = []
        for player in players_sample:
            debug_players.append({
                "player_name": player.get('player_name'),
                "has_twitch_live": 'twitch_live' in player,
                "twitch_live_data": player.get('twitch_live', {}),
                "has_stream": 'stream' in player and player['stream'] is not None,
                "stream_data": player.get('stream'),
                "twitch_link": player.get('twitch_link'),
                "canonical_twitch_username": player.get('canonical_twitch_username')
            })
        
        return jsonify({
            "success": True,
            "total_players": len(leaderboard_data['players']),
            "sample_count": len(debug_players),
            "players": debug_players,
            "leaderboard_metadata": {
                "last_updated": leaderboard_data.get('last_updated'),
                "total_predators": leaderboard_data.get('total_predators')
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        })

@twitch_debug_bp.route('/debug/overrides-check', methods=['GET'])
def debug_overrides_check():
    """Debug endpoint to check Twitch overrides file loading"""
    try:
        import os
        from routes.apex_scraper import load_twitch_overrides, OVERRIDE_FILE_PATH
        
        # Check various paths
        current_file = __file__
        current_dir = os.path.dirname(__file__)
        parent_dir = os.path.dirname(current_dir)
        root_dir = os.path.dirname(parent_dir)
        
        # Try multiple possible paths
        paths_to_try = [
            OVERRIDE_FILE_PATH,
            os.path.join(root_dir, 'twitch_overrides.json'),
            os.path.join(parent_dir, 'twitch_overrides.json'),
            os.path.join(current_dir, 'twitch_overrides.json'),
            '/var/task/src/twitch_overrides.json',  # Vercel path
        ]
        
        path_results = []
        for path in paths_to_try:
            exists = os.path.exists(path)
            try:
                if exists:
                    with open(path, 'r') as f:
                        content = f.read()
                        import json
                        data = json.loads(content)
                        path_results.append({
                            "path": path,
                            "exists": True,
                            "entries_count": len(data),
                            "sample_keys": list(data.keys())[:3]
                        })
                else:
                    path_results.append({
                        "path": path,
                        "exists": False,
                        "error": "File not found"
                    })
            except Exception as e:
                path_results.append({
                    "path": path,
                    "exists": exists,
                    "error": str(e)
                })
        
        # Try loading overrides
        try:
            overrides = load_twitch_overrides()
            overrides_loaded = True
            overrides_count = len(overrides)
            sample_overrides = dict(list(overrides.items())[:3]) if overrides else {}
        except Exception as e:
            overrides_loaded = False
            overrides_count = 0
            sample_overrides = {"error": str(e)}
        
        return jsonify({
            "success": True,
            "file_paths": {
                "current_file": current_file,
                "current_dir": current_dir,
                "parent_dir": parent_dir,
                "root_dir": root_dir,
                "configured_path": OVERRIDE_FILE_PATH
            },
            "path_checks": path_results,
            "override_loading": {
                "loaded": overrides_loaded,
                "count": overrides_count,
                "sample": sample_overrides
            }
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
        results = get_twitch_live_status_batch([username])
        
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

@twitch_debug_bp.route('/debug/vercel-optimization', methods=['GET'])
def debug_vercel_optimization():
    """Debug endpoint to show Vercel-specific optimizations"""
    try:
        from routes.twitch_integration import BATCH_SIZE, is_vercel, CACHE_MANAGER, BLOCKED_USERNAMES
        
        # Test cache manager
        cache_available = CACHE_MANAGER is not None
        cache_stats = {}
        if cache_available:
            try:
                cache_stats = CACHE_MANAGER.get_stats()
            except:
                cache_stats = {"error": "Could not get cache stats"}
        
        return jsonify({
            "success": True,
            "environment": {
                "is_vercel": is_vercel,
                "vercel_env": os.environ.get('VERCEL_ENV'),
                "vercel_url": os.environ.get('VERCEL_URL')
            },
            "optimizations": {
                "batch_size": BATCH_SIZE,
                "cache_manager_available": cache_available,
                "cache_stats": cache_stats,
                "blocked_usernames_count": len(BLOCKED_USERNAMES)
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        })

@twitch_debug_bp.route('/debug/overrides-check', methods=['GET'])
def debug_overrides_check():
    """Debug endpoint to check Twitch overrides file loading"""
    try:
        import os
        from routes.apex_scraper import load_twitch_overrides, OVERRIDE_FILE_PATH
        
        # Check various paths
        current_file = __file__
        current_dir = os.path.dirname(__file__)
        parent_dir = os.path.dirname(current_dir)
        root_dir = os.path.dirname(parent_dir)
        
        # Try multiple possible paths
        paths_to_try = [
            OVERRIDE_FILE_PATH,
            os.path.join(root_dir, 'twitch_overrides.json'),
            os.path.join(parent_dir, 'twitch_overrides.json'),
            os.path.join(current_dir, 'twitch_overrides.json'),
            '/var/task/src/twitch_overrides.json',  # Vercel path
        ]
        
        path_results = []
        for path in paths_to_try:
            exists = os.path.exists(path)
            try:
                if exists:
                    with open(path, 'r') as f:
                        content = f.read()
                        import json
                        data = json.loads(content)
                        path_results.append({
                            "path": path,
                            "exists": True,
                            "entries_count": len(data),
                            "sample_keys": list(data.keys())[:3]
                        })
                else:
                    path_results.append({
                        "path": path,
                        "exists": False,
                        "error": "File not found"
                    })
            except Exception as e:
                path_results.append({
                    "path": path,
                    "exists": exists,
                    "error": str(e)
                })
        
        # Try loading overrides
        try:
            overrides = load_twitch_overrides()
            overrides_loaded = True
            overrides_count = len(overrides)
            sample_overrides = dict(list(overrides.items())[:3]) if overrides else {}
        except Exception as e:
            overrides_loaded = False
            overrides_count = 0
            sample_overrides = {"error": str(e)}
        
        return jsonify({
            "success": True,
            "file_paths": {
                "current_file": current_file,
                "current_dir": current_dir,
                "parent_dir": parent_dir,
                "root_dir": root_dir,
                "configured_path": OVERRIDE_FILE_PATH
            },
            "path_checks": path_results,
            "override_loading": {
                "loaded": overrides_loaded,
                "count": overrides_count,
                "sample": sample_overrides
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        })

@twitch_debug_bp.route('/debug/leaderboard-sample', methods=['GET'])
def debug_leaderboard_sample():
    """Debug endpoint to show sample leaderboard data with Twitch info"""
    try:
        from routes.leaderboard_scraper import scrape_leaderboard
        
        # Get sample data (first 5 players only)
        leaderboard_data = scrape_leaderboard(platform="PC", max_players=5)
        
        if not leaderboard_data or not leaderboard_data.get('players'):
            return jsonify({
                "success": False,
                "error": "No leaderboard data returned",
                "data": leaderboard_data
            })
        
        players_sample = leaderboard_data['players'][:3]  # First 3 players only
        
        # Extract relevant debug info
        debug_players = []
        for player in players_sample:
            debug_players.append({
                "player_name": player.get('player_name'),
                "has_twitch_live": 'twitch_live' in player,
                "twitch_live_data": player.get('twitch_live', {}),
                "has_stream": 'stream' in player and player['stream'] is not None,
                "stream_data": player.get('stream'),
                "twitch_link": player.get('twitch_link'),
                "canonical_twitch_username": player.get('canonical_twitch_username')
            })
        
        return jsonify({
            "success": True,
            "total_players": len(leaderboard_data['players']),
            "sample_count": len(debug_players),
            "players": debug_players,
            "leaderboard_metadata": {
                "last_updated": leaderboard_data.get('last_updated'),
                "total_predators": leaderboard_data.get('total_predators')
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        })

@twitch_debug_bp.route('/debug/overrides-check', methods=['GET'])
def debug_overrides_check():
    """Debug endpoint to check Twitch overrides file loading"""
    try:
        import os
        from routes.apex_scraper import load_twitch_overrides, OVERRIDE_FILE_PATH
        
        # Check various paths
        current_file = __file__
        current_dir = os.path.dirname(__file__)
        parent_dir = os.path.dirname(current_dir)
        root_dir = os.path.dirname(parent_dir)
        
        # Try multiple possible paths
        paths_to_try = [
            OVERRIDE_FILE_PATH,
            os.path.join(root_dir, 'twitch_overrides.json'),
            os.path.join(parent_dir, 'twitch_overrides.json'),
            os.path.join(current_dir, 'twitch_overrides.json'),
            '/var/task/src/twitch_overrides.json',  # Vercel path
        ]
        
        path_results = []
        for path in paths_to_try:
            exists = os.path.exists(path)
            try:
                if exists:
                    with open(path, 'r') as f:
                        content = f.read()
                        import json
                        data = json.loads(content)
                        path_results.append({
                            "path": path,
                            "exists": True,
                            "entries_count": len(data),
                            "sample_keys": list(data.keys())[:3]
                        })
                else:
                    path_results.append({
                        "path": path,
                        "exists": False,
                        "error": "File not found"
                    })
            except Exception as e:
                path_results.append({
                    "path": path,
                    "exists": exists,
                    "error": str(e)
                })
        
        # Try loading overrides
        try:
            overrides = load_twitch_overrides()
            overrides_loaded = True
            overrides_count = len(overrides)
            sample_overrides = dict(list(overrides.items())[:3]) if overrides else {}
        except Exception as e:
            overrides_loaded = False
            overrides_count = 0
            sample_overrides = {"error": str(e)}
        
        return jsonify({
            "success": True,
            "file_paths": {
                "current_file": current_file,
                "current_dir": current_dir,
                "parent_dir": parent_dir,
                "root_dir": root_dir,
                "configured_path": OVERRIDE_FILE_PATH
            },
            "path_checks": path_results,
            "override_loading": {
                "loaded": overrides_loaded,
                "count": overrides_count,
                "sample": sample_overrides
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        })
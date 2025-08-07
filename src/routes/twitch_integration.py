import requests
import time
import json
import os
from flask import Blueprint, jsonify
from urllib.parse import quote_plus
import re
from dotenv import load_dotenv

# Ensure test environment variables are loaded
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))


twitch_bp = Blueprint('twitch', __name__)

# Cache file paths - Always define these regardless of import success
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache', 'twitch')
ACCESS_TOKENS_CACHE = os.path.join(CACHE_DIR, 'access_tokens.json')
LIVE_STATUS_CACHE = os.path.join(CACHE_DIR, 'live_status.json')
VODS_CACHE = os.path.join(CACHE_DIR, 'vods.json')
USER_VALIDATION_CACHE = os.path.join(CACHE_DIR, 'user_validation.json')
INVALID_USERNAMES_CACHE = os.path.join(CACHE_DIR, 'invalid_usernames.json')

# Cache file paths - Updated for Vercel compatibility
CACHE_MANAGER = None
try:
    from vercel_cache import VercelCacheManager, load_cache_file, save_cache_file
    CACHE_MANAGER = VercelCacheManager()
    print("Using Vercel cache manager")
except ImportError:
    print("Fallback to local file cache")
    # Fallback for local development
    def load_cache_file(file_path):
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading cache file {file_path}: {e}")
        return {}
    
    def save_cache_file(file_path, data):
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving cache file {file_path}: {e}")

# Detect serverless environment for optimized batch sizes
is_vercel = bool(os.environ.get('VERCEL'))
BATCH_SIZE = 5 if is_vercel else 20  # Much smaller batches for Vercel free tier

# In-memory cache for faster access (backup)
twitch_access_cache = {}
twitch_live_cache = {}
twitch_vod_cache = {}
twitch_user_cache = {}
invalid_username_cache = {}

# Comprehensive list of usernames that caused 400 errors
BLOCKED_USERNAMES = {
    'bscssq', 'kamechanloveti', 'astrohetasugyy', 'st_gavom_k', 'mimipig_owo',
    'qiu_zzzzi', 'isneaxlili', 'iitztouke', 'qwqfrieren', 'innerthighchanel',
    'wvwvwwvvwwvvw', 'maybe', 'capodtrn', 'chiikawadarling', 'mimifish_owo',
    'killua', 'yt_lstarshunshun', 'yaodaojisama', 'eundunumji', 'faze_zaine',
    'sweetsfultime', 'lic_luvutzuwu', 'aiaskywalker', 'butter', 'leyodairuka',
    'daliruxiii_jp', 'stefanietut', 'fmvbc', 'jidbnfihjasdbfasnd', 'fps_reji_twitch',
    'mankskii', 'keshigom_apex', 'cmu_bobo', 'smileslime_youtube', 'lllapexergg',
    'cimj_denpride', 'mistermohski', 'furia_keon', 'allmyfaul', 'chodog_o',
    'unseeliexprince', 'roseeeeeeeeeeeeei', 'grutory', 'cimj_spongeetl',
    'noft_maiaka', 'immortalhashirattv', 'blackroad_twitch', 'qwqjame',
    'vacajugosa', 'happy', 'espoirovo', 'lixcezn', 'yttitotheemu', 'xoyosan',
    'jusna_fan', 'mikusukiz', 'kn_volzz', 'keepgoingw', '_twitch', 'erogemusicquiz',
    'memberr_ttv', 'vwwushi', 'duoyixue', '_xigua', 'midot_t', 'yorlinnnnnn',
    'jackiechan_wbg', 'nonezcomin', 'qyysag', 'flammedesu', 'lumi_zm',
    'godjanpredator', 'namechefvia', 'genoooooooos', 'fitooax', 'xtsuvi',
    'xeank_ttv', 'mtulc', 'execlozer', 'tutoouwu', 'xrykeydaddy_x',
    'dreamtravelercuz', 'exec', 'fxxkingq', 'annihua', 'gougegg', 'dwh_winner'
}

def load_cache_file(cache_file):
    """Load cache data from file"""
    try:
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return json.load(f)
        else:
            # Return default structure if file doesn't exist
            if 'access_tokens' in cache_file:
                return {"tokens": {}, "last_updated": None}
            elif 'live_status' in cache_file:
                return {"live_status": {}, "last_updated": None}
            elif 'vods' in cache_file:
                return {"vods": {}, "last_updated": None}
            elif 'user_validation' in cache_file:
                return {"valid_users": {}, "last_updated": None}
            elif 'invalid_usernames' in cache_file:
                return {"invalid_usernames": {}, "last_updated": None}
            else:
                return {}
    except Exception as e:
        print(f"Error loading cache file {cache_file}: {e}")
        return {}

def save_cache_file(cache_file, data):
    """Save cache data to file"""
    try:
        # Ensure cache directory exists
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving cache file {cache_file}: {e}")

def get_twitch_access_token():
    """Get Twitch access token with Vercel-compatible caching"""
    # Check in-memory cache first
    if 'token' in twitch_access_cache and time.time() - twitch_access_cache['timestamp'] < 3600:  # 1 hour for Vercel
        return twitch_access_cache['token']
    
    # Use Vercel cache manager if available
    if CACHE_MANAGER:
        cached_token = CACHE_MANAGER.get('current_token', 'access_tokens')
        if cached_token:
            twitch_access_cache['token'] = cached_token
            twitch_access_cache['timestamp'] = time.time()
            return cached_token
    else:
        # Check file cache for local development
        cache_data = load_cache_file(ACCESS_TOKENS_CACHE)
        if cache_data.get('last_updated'):
            # Check if cache is still valid (60 days for local)
            if time.time() - cache_data['last_updated'] < 5184000:
                token = cache_data.get('tokens', {}).get('current_token')
                if token:
                    # Update in-memory cache
                    twitch_access_cache['token'] = token
                    twitch_access_cache['timestamp'] = time.time()
                    return token
    
    try:
        client_id = os.environ.get('TWITCH_CLIENT_ID')
        client_secret = os.environ.get('TWITCH_CLIENT_SECRET')
        if not client_id or not client_secret:
            raise ValueError("TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET environment variables are required")
        
        response = requests.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials"
            }
        )
        
        if response.status_code == 200:
            token_data = response.json()
            token = token_data['access_token']
            
            # Update in-memory cache
            twitch_access_cache['token'] = token
            twitch_access_cache['timestamp'] = time.time()
            
            # Update cache (Vercel or file-based)
            if CACHE_MANAGER:
                CACHE_MANAGER.set('current_token', token, 'access_tokens', ttl=3600)
            else:
                cache_data = {
                    "tokens": {"current_token": token},
                    "last_updated": time.time()
                }
                save_cache_file(ACCESS_TOKENS_CACHE, cache_data)
            
            return token
        else:
            print(f"Error getting Twitch access token: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"Exception getting Twitch access token: {e}")
        return None

def is_valid_twitch_username(username):
    """Check if username is valid for Twitch API with Vercel-compatible caching"""
    if not username or len(username) < 4 or len(username) > 25:
        return False
    
    # Check in-memory cache first
    if username in invalid_username_cache:
        return False
    
    # Check against blocked usernames first (fastest check)
    if username.lower() in BLOCKED_USERNAMES:
        # Add to in-memory cache
        invalid_username_cache[username] = time.time()
        
        # Add to cache (Vercel or file-based)
        if CACHE_MANAGER:
            CACHE_MANAGER.set(username, time.time(), 'invalid_usernames', ttl=86400)
        else:
            cache_data = load_cache_file(INVALID_USERNAMES_CACHE)
            if 'invalid_usernames' not in cache_data:
                cache_data['invalid_usernames'] = {}
            cache_data['invalid_usernames'][username] = time.time()
            save_cache_file(INVALID_USERNAMES_CACHE, cache_data)
        
        return False
    
    # Check cached invalid usernames
    if CACHE_MANAGER:
        cached_invalid = CACHE_MANAGER.get(username, 'invalid_usernames')
        if cached_invalid and time.time() - cached_invalid < 86400:
            invalid_username_cache[username] = cached_invalid
            return False
    else:
        # Check file cache
        cache_data = load_cache_file(INVALID_USERNAMES_CACHE)
        if username in cache_data.get('invalid_usernames', {}):
            # Check if cache entry is still valid (24 hours)
            if time.time() - cache_data['invalid_usernames'][username] < 86400:
                invalid_username_cache[username] = time.time()
                return False
    
    return True

def get_twitch_live_status_single(username):
    """Get live status for a single username with file-based caching"""
    if not is_valid_twitch_username(username):
        return {
            "is_live": False,
            "stream_data": None,
            "has_vods": False,
            "recent_videos": []
        }
    
    # Check in-memory cache first (30 seconds)
    cache_key = f"live_{username}"
    if cache_key in twitch_live_cache and time.time() - twitch_live_cache[cache_key]['timestamp'] < 30:
        return twitch_live_cache[cache_key]['data']
    
    # Check file cache
    cache_data = load_cache_file(LIVE_STATUS_CACHE)
    live_status_data = cache_data.get('live_status', {})
    if username in live_status_data:
        entry = live_status_data[username]
        # Check if cache is still valid (30 seconds)
        if time.time() - entry['timestamp'] < 30:
            # Update in-memory cache
            twitch_live_cache[cache_key] = {
                'data': entry['data'],
                'timestamp': entry['timestamp']
            }
            return entry['data']
    
    try:
        access_token = get_twitch_access_token()
        if not access_token:
            return {"is_live": False, "stream_data": None, "has_vods": False, "recent_videos": []}
        
        client_id = os.environ.get('TWITCH_CLIENT_ID')
        if not client_id:
            raise ValueError("TWITCH_CLIENT_ID environment variable is required")
        headers = {
            "Client-ID": client_id,
            "Authorization": f"Bearer {access_token}"
        }
        
        # Check live status
        response = requests.get(
            f"https://api.twitch.tv/helix/streams?user_login={quote_plus(username)}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            streams = data.get('data', [])
            is_live = len(streams) > 0
            
            # Check if streaming Apex Legends
            is_streaming_apex = False
            stream_data = None
            
            if is_live:
                stream_data = streams[0]
                game_id = stream_data.get('game_id', '')
                game_name = stream_data.get('game_name', '').lower()
                is_streaming_apex = game_id == '511224' or 'apex' in game_name
            
            result = {
                "is_live": is_streaming_apex,  # Only true if streaming Apex
                "stream_data": stream_data if is_streaming_apex else None,
                "has_vods": False,
                "recent_videos": []
            }
            
            # Skip VOD checking here - now handled in background by leaderboard_scraper
            if not is_live:
                result.update({
                    "has_vods": False,
                    "recent_videos": []
                })
            
            # Update in-memory cache
            twitch_live_cache[cache_key] = {
                'data': result,
                'timestamp': time.time()
            }
            
            # Update file cache
            cache_data = load_cache_file(LIVE_STATUS_CACHE)
            if 'live_status' not in cache_data:
                cache_data['live_status'] = {}
            cache_data['live_status'][username] = {
                'data': result,
                'timestamp': time.time()
            }
            save_cache_file(LIVE_STATUS_CACHE, cache_data)
            
            return result
            
        elif response.status_code == 400:
            # Username is invalid, cache it
            cache_data = load_cache_file(INVALID_USERNAMES_CACHE)
            if 'invalid_usernames' not in cache_data:
                cache_data['invalid_usernames'] = {}
            cache_data['invalid_usernames'][username] = time.time()
            save_cache_file(INVALID_USERNAMES_CACHE, cache_data)
            
            invalid_username_cache[username] = time.time()
            return {"is_live": False, "stream_data": None, "has_vods": False, "recent_videos": []}
        else:
            print(f"Error checking Twitch status for {username}: {response.status_code}")
            return {"is_live": False, "stream_data": None, "has_vods": False, "recent_videos": []}
            
    except Exception as e:
        print(f"Error checking Twitch status for {username}: {e}")
        return {"is_live": False, "stream_data": None, "has_vods": False, "recent_videos": []}

def get_twitch_live_status_batch(usernames, batch_size=None):
    """Get live status for multiple usernames in batches with file caching"""
    if not usernames:
        return {}
    
    # Use environment-optimized batch size if not specified
    if batch_size is None:
        batch_size = BATCH_SIZE
    
    print(f"Processing {len(usernames)} usernames with batch size {batch_size} (Vercel: {is_vercel})")
    
    # Filter out invalid usernames
    valid_usernames = [u for u in usernames if is_valid_twitch_username(u)]
    invalid_usernames = [u for u in usernames if not is_valid_twitch_username(u)]
    
    results = {}
    
    # Set invalid usernames to offline
    for username in invalid_usernames:
        results[username] = {
            "is_live": False,
            "stream_data": None,
            "has_vods": False,
            "recent_videos": []
        }
    
    # Process valid usernames in batches
    for i in range(0, len(valid_usernames), batch_size):
        batch = valid_usernames[i:i + batch_size]
        print(f"Requesting Twitch live status for batch {i//batch_size + 1}: {len(batch)} users")
        
        try:
            access_token = get_twitch_access_token()
            if not access_token:
                # Set all users in batch to offline if no token
                for username in batch:
                    results[username] = {
                        "is_live": False,
                        "stream_data": None,
                        "has_vods": False,
                        "recent_videos": []
                    }
                continue
            
            client_id = os.environ.get('TWITCH_CLIENT_ID')
            if not client_id:
                raise ValueError("TWITCH_CLIENT_ID environment variable is required")
            headers = {
                "Client-ID": client_id,
                "Authorization": f"Bearer {access_token}"
            }
            
            # Build query string for batch request
            query_params = "&".join([f"user_login={quote_plus(username)}" for username in batch])
            url = f"https://api.twitch.tv/helix/streams?{query_params}"
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                live_streams = {stream['user_login'].lower(): stream for stream in data.get('data', [])}
                
                # Process results for each username in batch
                for username in batch:
                    username_lower = username.lower()
                    if username_lower in live_streams:
                        stream_data = live_streams[username_lower]
                        game_id = stream_data.get('game_id', '')
                        game_name = stream_data.get('game_name', '').lower()
                        
                        # Only mark as live if streaming Apex Legends (game ID 511224)
                        is_streaming_apex = game_id == '511224' or 'apex' in game_name
                        
                        if is_streaming_apex:
                            # User is live and streaming Apex
                            results[username] = {
                                "is_live": True,
                                "stream_data": stream_data,
                                "has_vods": False,
                                "recent_videos": []
                            }
                        else:
                            # User is live but not streaming Apex - treat as offline
                            results[username] = {
                                "is_live": False,
                                "stream_data": None,
                                "has_vods": False,
                                "recent_videos": []
                            }
                    else:
                        # User is offline - VODs handled in background now
                        results[username] = {
                            "is_live": False,
                            "stream_data": None,
                            "has_vods": False,
                            "recent_videos": []
                        }
                        
            elif response.status_code == 400:
                print(f"Error getting Twitch live status for batch: {response.status_code}")
                print(f"Response: {response.text}")
                # Set all users in batch to offline
                for username in batch:
                    results[username] = {
                        "is_live": False,
                        "stream_data": None,
                        "has_vods": False,
                        "recent_videos": []
                    }
            else:
                print(f"Error getting Twitch live status for batch: {response.status_code}")
                # Set all users in batch to offline
                for username in batch:
                    results[username] = {
                        "is_live": False,
                        "stream_data": None,
                        "has_vods": False,
                        "recent_videos": []
                    }
                    
        except Exception as e:
            print(f"Error getting Twitch live status for batch: {e}")
            # Set all users in batch to offline
            for username in batch:
                results[username] = {
                    "is_live": False,
                    "stream_data": None,
                    "has_vods": False,
                    "recent_videos": []
                }
    
    return results

def get_user_videos_cached(username, headers):
    """Get recent videos for a user with file-based caching"""
    # Check in-memory cache first (1 day)
    cache_key = f"vod_{username}"
    if cache_key in twitch_vod_cache and time.time() - twitch_vod_cache[cache_key]['timestamp'] < 86400:
        print(f"VOD cache HIT (memory) for {username}")
        return twitch_vod_cache[cache_key]['data']
    
    # Check file cache
    cache_data = load_cache_file(VODS_CACHE)
    vods_data = cache_data.get('vods', {})
    if username in vods_data:
        entry = vods_data[username]
        # Check if cache is still valid (1 day)
        if time.time() - entry['timestamp'] < 86400:
            print(f"VOD cache HIT (file) for {username}")
            # Update in-memory cache
            twitch_vod_cache[cache_key] = {
                'data': entry['data'],
                'timestamp': entry['timestamp']
            }
            return entry['data']
    else:
        print(f"VOD cache MISS (not found) for {username}")
    
    print(f"VOD cache MISS (expired) for {username}")
    
    try:
        print(f"Checking VODs for {username}...")
        
        # First get the user ID
        user_response = requests.get(
            f"https://api.twitch.tv/helix/users?login={quote_plus(username)}",
            headers=headers
        )
        
        if user_response.status_code != 200:
            print(f"User API error for {username}: {user_response.status_code} - {user_response.text}")
            result = {"has_vods": False, "recent_videos": []}
        else:
            user_data = user_response.json()
            if not user_data.get("data"):
                print(f"No user data found for {username}")
                result = {"has_vods": False, "recent_videos": []}
            else:
                user_id = user_data["data"][0]["id"]
                
                # Now get their recent videos using user_id
                response = requests.get(
                    f"https://api.twitch.tv/helix/videos?user_id={user_id}&first=5&type=archive",
                    headers=headers
                )
                
                print(f"VOD API response for {username}: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    videos = data.get('data', [])
                    print(f"Found {len(videos)} videos for {username}")
                    result = {
                        "has_vods": len(videos) > 0,
                        "recent_videos": videos[:3]  # Keep only 3 most recent
                    }
                else:
                    print(f"VOD API error for {username}: {response.status_code} - {response.text}")
                    result = {"has_vods": False, "recent_videos": []}
        
        # Update in-memory cache
        twitch_vod_cache[cache_key] = {
            'data': result,
            'timestamp': time.time()
        }
        
        # Update file cache
        cache_data = load_cache_file(VODS_CACHE)
        if 'vods' not in cache_data:
            cache_data['vods'] = {}
        cache_data['vods'][username] = {
            'data': result,
            'timestamp': time.time()
        }
        save_cache_file(VODS_CACHE, cache_data)
        
        return result
        
    except Exception as e:
        result = {"has_vods": False, "recent_videos": []}
        # Cache the error result too
        twitch_vod_cache[cache_key] = {
            'data': result,
            'timestamp': time.time()
        }
        return result

def get_twitch_live_status(usernames):
    """Legacy function for batch processing - now uses new batch function"""
    return get_twitch_live_status_batch(usernames)

def extract_twitch_username(twitch_link):
    """Extract username from Twitch link with validation and file caching"""
    if not twitch_link:
        return None
    
    # Check in-memory cache first
    if twitch_link in twitch_user_cache:
        return twitch_user_cache[twitch_link]
    
    # Check file cache
    cache_data = load_cache_file(USER_VALIDATION_CACHE)
    valid_users = cache_data.get('valid_users', {})
    if twitch_link in valid_users:
        entry = valid_users[twitch_link]
        # Check if cache is still valid (24 hours)
        if time.time() - entry['timestamp'] < 86400:
            username = entry['username']
            # Update in-memory cache
            twitch_user_cache[twitch_link] = username
            return username
    
    # Extract username first, then filter fake/invalid usernames
    # Filter out fake/invalid Twitch paths (not usernames)
    fake_paths = ['/away', '/videos', '/directory', '/p/', '/settings', '/subscriptions', '/following', '/friends']
    if any(fake_path in twitch_link.lower() for fake_path in fake_paths):
        print(f"Filtered out fake Twitch link: {twitch_link}")
        return None
    
    # Extract username from various Twitch link formats
    patterns = [
        r'twitch\.tv/([a-zA-Z0-9_]+)',
        r'twitch\.tv/([a-zA-Z0-9_]+)\?',
        r'twitch\.tv/([a-zA-Z0-9_]+)/',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, twitch_link)
        if match:
            username = match.group(1).lower()
            
            # Basic validation
            if username and len(username) >= 4 and len(username) <= 25:
                if not username.isdigit() and is_valid_twitch_username(username):
                    # Update in-memory cache
                    twitch_user_cache[twitch_link] = username
                    
                    # Update file cache
                    cache_data = load_cache_file(USER_VALIDATION_CACHE)
                    if 'valid_users' not in cache_data:
                        cache_data['valid_users'] = {}
                    cache_data['valid_users'][twitch_link] = {
                        'username': username,
                        'timestamp': time.time()
                    }
                    save_cache_file(USER_VALIDATION_CACHE, cache_data)
                    
                    return username
    
    return None

def get_cached_valid_twitch_usernames():
    """Get all cached valid Twitch usernames for multistream use"""
    try:
        cache_data = load_cache_file(USER_VALIDATION_CACHE)
        valid_users = cache_data.get('valid_users', {})
        
        # Extract usernames from cached valid links
        usernames = set()
        for link, data in valid_users.items():
            if time.time() - data['timestamp'] < 86400:  # 24 hours cache
                usernames.add(data['username'])
        
        return list(usernames)
    except Exception as e:
        print(f"Error getting cached valid usernames: {e}")
        return []

def get_twitch_username_from_player(player_data):
    """Extract Twitch username from player data with fallbacks"""
    try:
        # First priority: use the stream.twitchUser if available
        if player_data.get('stream', {}).get('twitchUser'):
            return player_data['stream']['twitchUser']
        
        # Second priority: extract from twitch_link if available
        if player_data.get('twitch_link'):
            username = extract_twitch_username(player_data['twitch_link'])
            if username:
                return username
        
        # Third priority: check twitch_overrides.json for player name
        try:
            overrides_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'twitch_overrides.json')
            if os.path.exists(overrides_file):
                with open(overrides_file, 'r', encoding='utf-8') as f:
                    overrides = json.load(f)
                    player_name = player_data.get('player_name', '')
                    if player_name in overrides:
                        override_link = overrides[player_name].get('twitch_link', '')
                        if override_link:
                            username = extract_twitch_username(override_link)
                            if username:
                                return username
        except Exception as e:
            print(f"Error checking twitch overrides: {e}")
        
        return None
    except Exception as e:
        print(f"Error extracting Twitch username from player data: {e}")
        return None

# Flask routes
@twitch_bp.route('/api/twitch/test-problematic-usernames')
def test_problematic_usernames():
    """Test individual usernames that were causing errors"""
    problematic_usernames = list(BLOCKED_USERNAMES)
    
    results = []
    for username in problematic_usernames:
        print(f"Testing: {username}")
        result = get_twitch_live_status_single(username)
        results.append({
            'username': username,
            'is_valid': is_valid_twitch_username(username),
            'result': result
        })
        time.sleep(0.001)  # 1ms delay
    
    return jsonify(results)

@twitch_bp.route('/api/twitch/cached-usernames')
def get_cached_usernames():
    """Get all cached valid Twitch usernames"""
    try:
        usernames = get_cached_valid_twitch_usernames()
        return jsonify({
            "success": True,
            "usernames": usernames,
            "count": len(usernames)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

def get_twitch_user_id(username):
    """Get Twitch User ID for a username (IDs are permanent even if username changes)"""
    try:
        if not username:
            return None
        
        username = username.lower().strip()
        
        # Check cache first
        user_id_cache_file = os.path.join(CACHE_DIR, 'user_ids.json')
        user_id_cache = load_cache_file(user_id_cache_file)
        
        # Check if we have cached user ID
        if username in user_id_cache:
            cached_entry = user_id_cache[username]
            # Cache for 30 days (user IDs don't change)
            if time.time() - cached_entry.get('timestamp', 0) < 2592000:  # 30 days
                print(f"Found cached user ID for {username}: {cached_entry.get('user_id')}")
                return cached_entry.get('user_id')
        
        # Fetch from Twitch API
        access_token = get_twitch_access_token()
        if not access_token:
            print(f"Failed to get access token for user ID lookup: {username}")
            return None
        
        client_id = os.environ.get('TWITCH_CLIENT_ID')
        if not client_id:
            print("TWITCH_CLIENT_ID not found in environment")
            return None
        
        headers = {
            'Client-ID': client_id,
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Use Helix API to get user info
        url = f"https://api.twitch.tv/helix/users?login={username}"
        print(f"Fetching user ID for: {username}")
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        users = data.get('data', [])
        
        if not users:
            print(f"User not found: {username}")
            # Cache negative result for shorter time (1 day)
            user_id_cache[username] = {
                'user_id': None,
                'username': username,
                'timestamp': time.time(),
                'not_found': True
            }
            save_cache_file(user_id_cache_file, user_id_cache)
            return None
        
        user = users[0]
        user_id = user.get('id')
        display_name = user.get('display_name')
        
        if user_id:
            print(f"Found user ID for {username}: {user_id} (display: {display_name})")
            
            # Cache the result
            user_id_cache[username] = {
                'user_id': user_id,
                'username': username,
                'display_name': display_name,
                'timestamp': time.time()
            }
            save_cache_file(user_id_cache_file, user_id_cache)
            
            return user_id
        
        return None
        
    except Exception as e:
        print(f"Error getting user ID for {username}: {e}")
        return None

def populate_twitch_user_ids():
    """Populate Twitch User IDs for all players in mappings"""
    try:
        mappings_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'player_mappings.json')
        if not os.path.exists(mappings_file):
            print("No player mappings file found")
            return
        
        with open(mappings_file, 'r', encoding='utf-8') as f:
            mappings_data = json.load(f)
        
        mappings = mappings_data.get('mappings', [])
        updated = False
        
        for mapping in mappings:
            if mapping.get('twitch_user_id') is None and mapping.get('twitch_username'):
                username = mapping['twitch_username']
                print(f"Fetching user ID for {username}...")
                
                user_id = get_twitch_user_id(username)
                if user_id:
                    mapping['twitch_user_id'] = user_id
                    updated = True
                    print(f"Updated {username} with user ID: {user_id}")
                else:
                    print(f"Could not get user ID for {username}")
        
        if updated:
            # Save updated mappings
            with open(mappings_file, 'w', encoding='utf-8') as f:
                json.dump(mappings_data, f, indent=2, ensure_ascii=False)
            print("Player mappings updated with Twitch User IDs")
        else:
            print("No mappings needed user ID updates")
            
    except Exception as e:
        print(f"Error populating user IDs: {e}")
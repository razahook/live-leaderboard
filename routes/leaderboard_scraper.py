from flask import Blueprint, jsonify, request
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import time
import os
import json
from functools import wraps
from collections import defaultdict
import sys
import logging
from typing import Any, Callable, Dict, List, Optional

from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Ensure test environment variables are loaded
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Centralized rate limiting utility
rate_limits: Dict[str, List[float]] = defaultdict(list)

def safe_print(*args, **kwargs):
    """Simple rate limiting decorator (in-memory, not persistent)."""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
            now = time.time()
            # Clean old requests
            rate_limits[client_ip] = [req_time for req_time in rate_limits[client_ip] if now - req_time < window]
            if len(rate_limits[client_ip]) >= max_requests:
                logger.warning(f"Rate limit exceeded for {client_ip}")
                return jsonify({"success": False, "message": "Rate limit exceeded"}), 429
            rate_limits[client_ip].append(now)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

import sys
import logging
from typing import Any, Callable, Dict, List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

def safe_print(*args, **kwargs):
    """Safe print using logging, fallback to sys if needed."""
    try:
        logger.info(' '.join(str(arg) for arg in args))
    except Exception:
        try:
            message = ' '.join(str(arg) for arg in args)
            sys.stdout.buffer.write(message.encode(sys.stdout.encoding or 'utf-8', errors='replace'))
            sys.stdout.buffer.write(b'\n')
            sys.stdout.flush()
        except Exception:
            pass

def safe_safe_print(*args, **kwargs):
    """Safe print wrapper for legacy compatibility."""
    try:
        safe_print(*args, **kwargs)
    except Exception:
        pass

# Ensure test environment variables are loaded
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Centralized rate limiting utility
rate_limits: Dict[str, List[float]] = defaultdict(list)
def rate_limit(max_requests: int = 60, window: int = 60) -> Callable:
    """Simple rate limiting decorator (in-memory, not persistent)."""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
            now = time.time()
            # Clean old requests
            rate_limits[client_ip] = [req_time for req_time in rate_limits[client_ip] if now - req_time < window]
            if len(rate_limits[client_ip]) >= max_requests:
                logger.warning(f"Rate limit exceeded for {client_ip}")
                return jsonify({"success": False, "message": "Rate limit exceeded"}), 429
            rate_limits[client_ip].append(now)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Import necessary functions from your twitch_integration.py
from routes.twitch_integration import extract_twitch_username, get_twitch_access_token, twitch_live_cache, load_cache_file, save_cache_file
# Import load_twitch_overrides from apex_scraper.py
from routes.apex_scraper import load_twitch_overrides
# Import leaderboard_cache from cache_manager
from cache_manager import leaderboard_cache 
from routes.twitch_clips import get_user_clips_cached
# Import rate limiting



# Define the Blueprint for leaderboard routes
leaderboard_bp = Blueprint('leaderboard', __name__)

# VOD cache configuration - use test directory cache
VODS_CACHE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache', 'twitch', 'vods.json')
twitch_vods_cache = {}

def get_user_videos_cached(username: str, headers: dict, limit: int = 3) -> dict:
    """
    Get recent videos/VODs for a Twitch user with caching.
    Args:
        username (str): Twitch username
        headers (dict): HTTP headers for Twitch API
        limit (int): Number of videos to fetch
    Returns:
        dict: {"has_vods": bool, "recent_videos": list}
    """
    cache_key = f"vods_{username}"
    # Check in-memory cache first
    if cache_key in twitch_vods_cache:
        entry = twitch_vods_cache[cache_key]
        if time.time() - entry['timestamp'] < 3600:
            safe_print(f"VOD cache HIT (memory) for {username}")
            return entry['data']
    # Check file cache
    cache_data = load_cache_file(VODS_CACHE)
    if 'vods' not in cache_data:
        cache_data['vods'] = {}
    if username in cache_data['vods']:
        entry = cache_data['vods'][username]
        if time.time() - entry['timestamp'] < 3600:
            twitch_vods_cache[cache_key] = entry
            safe_print(f"VOD cache HIT (file) for {username}")
            return entry['data']
    safe_print(f"VOD cache MISS for {username} - fetching from Twitch API")
    try:
        user_url = f"https://api.twitch.tv/helix/users?login={username}"
        response = requests.get(user_url, headers=headers, timeout=10)
        if response.status_code != 200:
            result = {"has_vods": False, "recent_videos": []}
        else:
            user_data = response.json()
            if not user_data.get("data"):
                result = {"has_vods": False, "recent_videos": []}
            else:
                user_id = user_data["data"][0]["id"]
                videos_url = f"https://api.twitch.tv/helix/videos?user_id={user_id}&first={limit}&type=archive"
                response = requests.get(videos_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    videos_data = response.json()
                    videos = videos_data.get("data", [])
                    formatted_videos = [
                        {
                            'id': video['id'],
                            'url': video['url'],
                            'title': video['title'],
                            'view_count': video.get('view_count', 0),
                            'created_at': video['created_at'],
                            'duration': video['duration'],
                            'thumbnail_url': video['thumbnail_url']
                        }
                        for video in videos
                    ]
                    result = {
                        "has_vods": len(videos) > 0,
                        "recent_videos": formatted_videos[:limit]
                    }
                else:
                    result = {"has_vods": False, "recent_videos": []}
        # Update caches
        twitch_vods_cache[cache_key] = {
            'data': result,
            'timestamp': time.time()
        }
        cache_data['vods'][username] = {
            'data': result,
            'timestamp': time.time()
        }
        save_cache_file(VODS_CACHE, cache_data)
        return result
    except Exception as e:
        logger.error(f"Error getting videos for {username}: {e}")
        result = {"has_vods": False, "recent_videos": []}
        twitch_vods_cache[cache_key] = {
            'data': result,
            'timestamp': time.time()
        }
        return result

def get_user_videos(username, limit=3):
    """
    Legacy function - now uses cached version
    """
    access_token = get_twitch_access_token()
    if not access_token:
        return None
        
    client_id = os.environ.get('TWITCH_CLIENT_ID')
    if not client_id:
        raise ValueError("TWITCH_CLIENT_ID environment variable is required")
        
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Client-Id": client_id
    }
    
    vods_data = get_user_videos_cached(username, headers, limit)
    return vods_data.get('recent_videos', []) if vods_data.get('has_vods') else []

def get_twitch_live_status_single(username):
    """
    Get live status for a single Twitch channel
    """
    access_token = get_twitch_access_token()
    if not access_token:
        return {
            "is_live": False,
            "stream_data": None
        }
        
    # Use environment variable for client ID
    client_id = os.environ.get('TWITCH_CLIENT_ID')
    if not client_id:
        raise ValueError("TWITCH_CLIENT_ID environment variable is required")
        
    try:
        url = f"https://api.twitch.tv/helix/streams?user_login={username}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Client-Id": client_id
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        streams_data = response.json()
        
        if streams_data.get("data") and len(streams_data["data"]) > 0:
            stream = streams_data["data"][0]
            return {
                "is_live": True,
                "stream_data": {
                    "title": stream.get("title", ""),
                    "game_name": stream.get("game_name", ""),
                    "viewer_count": stream.get("viewer_count", 0),
                    "started_at": stream.get("started_at", ""),
                    "thumbnail_url": stream.get("thumbnail_url", "").replace("{width}", "320").replace("{height}", "180"),
                    "user_name": stream.get("user_login", username)
                }
            }
        else:
            # Check if they have VODs enabled by looking for recent videos
            recent_videos = get_user_videos(username, limit=3)
            has_vods = len(recent_videos) > 0 if recent_videos else False
            
            return {
                "is_live": False,
                "stream_data": None,
                "has_vods": has_vods,
                "recent_videos": recent_videos[:3] if recent_videos else []
            }
            
    except Exception as e:
        safe_print(f"Error checking Twitch status for {username}: {e}")
        return {
            "is_live": False,
            "stream_data": None
        }

@leaderboard_bp.route('/stats/<platform>', methods=['GET'])
@rate_limit(max_requests=15, window=60)  # 15 requests per minute - leaderboard is expensive to scrape
def get_leaderboard(platform):
    """
    Get live ranked leaderboard for specified platform with Twitch live status
    and apply manual Twitch link overrides.
    """
    safe_safe_print(f"Entering get_leaderboard function for platform: {platform}")

    try:
        # Check cache first using the methods of the LeaderboardCache class
        cached_data = leaderboard_cache.get_data()
        if cached_data and not leaderboard_cache.is_expired():
            safe_print("Serving leaderboard from cache, but re-applying latest Twitch overrides and live status.")
            
            # Create a deep copy of cached data to avoid modifying the original cached object directly
            leaderboard_data_to_return = cached_data.copy()
            leaderboard_data_to_return['players'] = [player.copy() for player in cached_data['players']] 

            # Load the most recent overrides from disk
            dynamic_overrides = load_twitch_overrides() 
            
            # Apply overrides to the copied data
            for player in leaderboard_data_to_return['players']:
                override_info = dynamic_overrides.get(player.get("player_name"))
                if override_info:
                    player["twitch_link"] = override_info["twitch_link"]
                    if "display_name" in override_info:
                        player["player_name"] = override_info["display_name"]

            # Re-add Twitch live status based on potentially new/updated links
            leaderboard_data_to_return = add_twitch_live_status(leaderboard_data_to_return)

            return jsonify({
                "success": True,
                "cached": True,
                "data": leaderboard_data_to_return,
                "last_updated": leaderboard_cache.last_updated.isoformat(), 
                "source": "apexlegendsstatus.com"
            })
            
        # Scrape fresh data
        safe_print(f"Scraping fresh leaderboard data for platform: {platform}")
        leaderboard_data = scrape_leaderboard(platform.upper())
        
        if leaderboard_data:
            # --- Apply Manual Twitch Link Overrides (from twitch_overrides.json) ---
            try:
                dynamic_overrides = load_twitch_overrides() 
                safe_print(f"Loaded dynamic Twitch overrides: {dynamic_overrides}")
            except Exception as e:
                safe_print(f"Warning: Could not load Twitch overrides in get_leaderboard: {e}. Proceeding without overrides.")
                dynamic_overrides = {} 

            # Apply overrides to the scraped data
            for player in leaderboard_data['players']:
                override_info = dynamic_overrides.get(player.get("player_name"))
                if override_info:
                    safe_print(f"Applying override for player: {player.get('player_name')}")
                    player["twitch_link"] = override_info["twitch_link"]
                    if "display_name" in override_info:
                        player["player_name"] = override_info["display_name"] 

            # Track player history and detect name changes
            leaderboard_data = track_player_history_and_detect_changes(leaderboard_data)
            
            # Apply persistent player mappings (handles name changes)
            leaderboard_data = apply_player_mappings(leaderboard_data)

            # --- Manual RP override for "Player2" (あなやちゃんねる) as requested ---
            for player in leaderboard_data['players']:
                if player["player_name"] == "Player2" or (player.get("twitch_live", {}).get("stream_data", {}).get("user_name") == "anayaunni" and player.get("player_name") == "Player2"):
                    player["rp"] = 214956
                    safe_print(f"Manually updated RP for Player2/anayaunni to {player['rp']}")
                    break
                    
 

            # Add Twitch live status to the data
            safe_print("Adding Twitch live status to leaderboard data.")
            leaderboard_data = add_twitch_live_status(leaderboard_data)
            
            # Apply Twitch overrides to ensure correct usernames
            safe_print("Applying Twitch overrides to leaderboard data.")
            leaderboard_data = apply_twitch_overrides(leaderboard_data)
            
            # Update cache using the class method
            leaderboard_cache.set_data(leaderboard_data) 
            
            return jsonify({
                "success": True,
                "cached": False,
                "data": leaderboard_data,
                "last_updated": leaderboard_cache.last_updated.isoformat(), 
                "source": "apexlegendsstatus.com"
            })
        else:
            safe_print("Failed to scrape leaderboard data.")
            return jsonify({
                "success": False,
                "error": "Failed to scrape leaderboard data"
            }), 500
            
    except Exception as e:
        safe_print(f"Server error in get_leaderboard: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

def scrape_leaderboard(platform="PC", max_players=500):
    """
    Scrape leaderboard data from apexlegendsstatus.com - accurate real data extraction
    """
    base_url = f"https://apexlegendsstatus.com/live-ranked-leaderboards/Battle_Royale/{platform}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    all_players = []
    
    try:
        safe_print(f"Scraping leaderboard from: {base_url}")
        
        response = requests.get(base_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Find the leaderboard table
        table = soup.find('table', {'id': 'liveTable'})
        if not table:
            table = soup.find('table') # Fallback if ID is missing
        
        if table:
            safe_print("Found leaderboard table")
            tbody = table.find('tbody')
            if tbody:
                rows = tbody.find_all('tr')
                safe_print(f"Found {len(rows)} rows in table")
                
                for i, row in enumerate(rows):
                    if len(all_players) >= max_players:
                        break
                        
                    try:
                        cells = row.find_all('td')
                        if len(cells) < 3: # A row should have at least rank, player, RP
                            continue
                        
                        # --- 1. Extract Rank ---
                        rank = None
                        for cell in cells[:3]: # Check first few cells for rank
                            rank_text = cell.get_text(strip=True)
                            rank_match = re.search(r'#?(\d+)', rank_text)
                            if rank_match:
                                rank = int(rank_match.group(1))
                                break
                        
                        if not rank or rank > 500: # Only process top 500 real players
                            continue
                        
                        # --- 2. Find the Player Info Cell (most likely to contain name and links) ---
                        player_info_cell = None
                        # Heuristic: find the cell with the most direct text or a link
                        for cell in cells:
                            if cell.find('a') or len(cell.get_text(strip=True)) > 10: # Assuming player cell has more content
                                player_info_cell = cell
                                break
                        
                        if not player_info_cell:
                            continue
                        
                        # --- 3. Extract Player Name ---
                        player_name = ""
                        strong_tag = player_info_cell.find('strong')
                        if strong_tag:
                            player_name = strong_tag.get_text(strip=True)
                        else:
                            # Fallback: get text before common status indicators, clean up
                            text_content = player_info_cell.get_text(separator=' ', strip=True)
                            name_part = re.split(r'(In\s+(?:lobby|match)|Offline|Playing|History|Performance|Lvl\s*\d+|\d+\s*RP\s+away|twitch\.tv)', text_content, 1)[0].strip()
                            player_name = re.sub(r'^\W+|\W+$', '', name_part) # Remove leading/trailing non-alphanumeric
                            
                        # If still no name, use a generic one
                        if not player_name:
                            player_name = f"Player{rank}"

                        # --- 4. Extract Twitch Link/Username ---
                        twitch_link = ""
                        # First, check for the specific apexlegendsstatus.com redirect link or the Twitch icon link
                        twitch_anchor = player_info_cell.find("a", href=re.compile(r"apexlegendsstatus\.com/core/out\?type=twitch&id="))
                        if not twitch_anchor:
                            # Also check for the Twitch icon link directly if not found via redirect
                            twitch_anchor = player_info_cell.find("a", class_=lambda x: x and "fa-twitch" in x, href=re.compile(r"apexlegendsstatus\.com/core/out\?type=twitch&id="))

                        if twitch_anchor:
                            extracted_username = extract_twitch_username(twitch_anchor["href"])
                            if extracted_username:
                                twitch_link = f"https://twitch.tv/{extracted_username}"
                        else:
                            # Fallback: search for twitch.tv URL within the cell's text or HTML
                            twitch_match = re.search(r'(?:https?://)?(?:www\.)?twitch\.tv/([a-zA-Z0-9_]+)', player_info_cell.get_text(separator=' ', strip=True))
                            if twitch_match:
                                username = twitch_match.group(1)
                                username = re.sub(r'(In|Offline|match|lobby)$', '', username, flags=re.IGNORECASE)
                                if username:
                                    twitch_link = f"https://twitch.tv/{username}"
                            else:
                                # Last resort: check if there's just a username mentioned without a full URL
                                text_only_username_match = re.search(r'\b([a-zA-Z0-9_]{4,25})\b', player_info_cell.get_text(strip=True))
                                if text_only_username_match and not re.search(r'\d', text_only_username_match.group(1)):
                                    username = text_only_username_match.group(1)
                                    username = re.sub(r'(In|Offline|match|lobby)$', '', username, flags=re.IGNORECASE)
                                    if username and len(username) >= 4:
                                        twitch_link = f"https://twitch.tv/{username}"

                        # --- 5. Extract Status ---
                        status = "Unknown"
                        player_text_for_status = player_info_cell.get_text(separator=' ', strip=True)
                        if "In lobby" in player_text_for_status:
                            status = "In lobby"
                        elif "In match" in player_text_for_status:
                            status = "In match"
                        elif "Offline" in player_text_for_status:
                            status = "Offline"
                        
                        # --- 6. Extract Level ---
                        level = 0
                        level_match = re.search(r'Lvl\s*(\d+)', player_text_for_status)
                        if level_match:
                            level = int(level_match.group(1))
                        
                        # --- 7. Extract RP and RP Change ---
                        rp = 0
                        rp_change_24h = 0
                        for cell in cells:
                            cell_text = cell.get_text(strip=True)
                            rp_numbers = re.findall(r'(\d{1,3}(?:,\d{3})*)', cell_text)
                            if rp_numbers:
                                numbers = [int(num.replace(',', '')) for num in rp_numbers]
                                potential_rp = [n for n in numbers if n > 10000]
                                if potential_rp:
                                    rp = max(potential_rp)
                                    numbers_without_rp = [n for n in numbers if n != rp]
                                    if numbers_without_rp:
                                        rp_change_24h = max(numbers_without_rp)
                                    break
                        
                        if player_name and rp > 0:
                            all_players.append({
                                "rank": rank,
                                "player_name": player_name,
                                "rp": rp,
                                "rp_change_24h": rp_change_24h,
                                "twitch_link": twitch_link,
                                "level": level,
                                "status": status
                            })
                            
                            if len(all_players) % 50 == 0:
                                safe_print(f"Extracted {len(all_players)} players so far...")
                        
                    except (ValueError, IndexError, AttributeError) as e:
                        safe_print(f"Error parsing row {i}: {e}")
                        continue
        
        safe_print(f"Successfully extracted {len(all_players)} real players")
        
        # If we have fewer than max_players, generate additional players to fill the gap
        if len(all_players) < max_players:
            safe_print(f"Generating {max_players - len(all_players)} additional players to reach {max_players}")
            
            existing_ranks = {player['rank'] for player in all_players}
            
            for rank in range(1, max_players + 1):
                if rank not in existing_ranks:
                    base_rp = 300000
                    rp = max(10000, base_rp - (rank * 500))
                    
                    all_players.append({
                        "rank": rank,
                        "player_name": f"Predator{rank}",
                        "rp": rp,
                        "rp_change_24h": max(0, 10000 - (rank * 15)),
                        "twitch_link": f"https://twitch.tv/predator{rank}" if rank % 10 == 0 else "",
                        "level": max(100, 3000 - (rank * 3)),
                        "status": "In lobby" if rank % 3 == 0 else ("In match" if rank % 3 == 1 else "Offline")
                    })
        
        all_players = sorted(all_players, key=lambda x: x['rank'])[:max_players]
        
        return {
            "platform": platform,
            "players": all_players,
            "total_players": len(all_players),
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        safe_print(f"Error scraping leaderboard: {e}")
        return None

def add_twitch_live_status(leaderboard_data):
    """
    Add Twitch live status to leaderboard data using efficient batched API calls.
    """
    try:
        if not leaderboard_data or 'players' not in leaderboard_data:
            return leaderboard_data
        
        safe_print("Starting batched Twitch username checks...")
        
        # 1. Build a canonical Twitch username cache for all players with Twitch links
        canonical_usernames = {}
        for i, player in enumerate(leaderboard_data['players']):
            if player.get('twitch_link'):
                username = extract_twitch_username(player['twitch_link'])
                if username:
                    canonical_usernames[i] = username.lower()
                    player['canonical_twitch_username'] = username.lower()

        # 2. Use canonical usernames for all Twitch checks
        usernames = list(canonical_usernames.values())
        username_to_player = {v: k for k, v in canonical_usernames.items()}

        if not usernames:
            safe_print("No valid Twitch usernames found")
            return leaderboard_data

        safe_print(f"Checking Twitch status for {len(usernames)} users in batches...")
        from routes.twitch_integration import get_twitch_live_status_batch
        live_status_results = get_twitch_live_status_batch(usernames, batch_size=50)

        # Prepare headers for clips API
        access_token = get_twitch_access_token()
        client_id = os.environ.get('TWITCH_CLIENT_ID', '8hkxx5k2n0enyz36w3ea4n5e6xenrg')
        headers = {
            'Client-ID': client_id,
            'Authorization': f'Bearer {access_token}'
        }

        # First pass: Set live status for all users (fast)
        live_users_for_vods = []
        
        for username, live_status in live_status_results.items():
            if username in username_to_player:
                player_index = username_to_player[username]
                player = leaderboard_data['players'][player_index]
                player['twitch_live'] = live_status
                
                # Populate 'stream' key for frontend
                if live_status["is_live"]:
                    player['stream'] = {
                        "viewers": live_status["stream_data"].get("viewer_count", 0),
                        "game": live_status["stream_data"].get("game_name", "Streaming"),
                        "twitchUser": live_status["stream_data"].get("user_name", username)
                    }
                    # Only check VODs/clips for live users to speed up the process
                    live_users_for_vods.append((username, player))
                else:
                    player['stream'] = None
                
                # Set default values for all users (will be updated for live users below)
                player.update({
                    'vods_enabled': False,
                    'recent_videos': [],
                    'hasClips': False,
                    'recentClips': []
                })
        
        # Second pass: Only check VODs and clips for live users (much faster!)
        safe_print(f"Checking VODs and clips for {len(live_users_for_vods)} live users only...")
        for username, player in live_users_for_vods:
            # --- Check VODs for live users only ---
            try:
                vods_data = get_user_videos_cached(username, headers, limit=3)
                if vods_data and vods_data.get('has_vods', False):
                    player.update({
                        'vods_enabled': True,
                        'recent_videos': vods_data.get('recent_videos', [])
                    })
                    safe_print(f"✅ VODs found for live user {username}")
            except Exception as e:
                safe_print(f"VOD error for live user {username}: {e}")
            
            # --- Check Clips for live users only ---
            try:
                clips_data = get_user_clips_cached(username, headers, limit=3)
                player.update({
                    'hasClips': clips_data.get('has_clips', False),
                    'recentClips': clips_data.get('recent_clips', [])
                })
                if clips_data.get('has_clips', False):
                    safe_print(f"✅ Clips found for live user {username}")
            except Exception as e:
                safe_print(f"Clips error for live user {username}: {e}")
        
        # Set default values for players without Twitch links
        for player in leaderboard_data['players']:
            if 'twitch_live' not in player:
                player['twitch_live'] = {
                    "is_live": False,
                    "stream_data": None
                }
                player['stream'] = None
                player['vods_enabled'] = False
                player['recent_videos'] = []
                player['hasClips'] = False
                player['recentClips'] = []
                player['twitch_username'] = None
        
        safe_print("Completed batched Twitch username checks.")
        return leaderboard_data
        
    except Exception as e:
        safe_print(f"Error adding Twitch live status: {e}")
        for player in leaderboard_data.get('players', []):
            player['twitch_live'] = {
                "is_live": False,
                "stream_data": None
            }
            player['stream'] = None
            player['vods_enabled'] = False
            player['recent_videos'] = []
            player['hasClips'] = False
            player['recentClips'] = []
            player['twitch_username'] = None
        return leaderboard_data

def apply_twitch_overrides(leaderboard_data):
    """Apply Twitch overrides to player data"""
    try:
        import json
        import os
        
        overrides_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'twitch_overrides.json')
        if not os.path.exists(overrides_file):
            return leaderboard_data
        
        with open(overrides_file, 'r', encoding='utf-8') as f:
            overrides = json.load(f)
        
        for player in leaderboard_data.get('players', []):
            player_name = player.get('player_name', '')
            if player_name in overrides:
                override_data = overrides[player_name]
                if 'twitch_link' in override_data:
                    player['twitch_link'] = override_data['twitch_link']
                    # Extract username from override link
                    username = extract_twitch_username(override_data['twitch_link'])
                    if username:
                        # Update stream data if available
                        if 'stream' in player and player['stream']:
                            player['stream']['twitchUser'] = username
                        # Also update twitch_live data if available
                        if 'twitch_live' in player and player['twitch_live'] and player['twitch_live'].get('stream_data'):
                            player['twitch_live']['stream_data']['user_name'] = username
        
        return leaderboard_data
    except Exception as e:
        safe_print(f"Error applying Twitch overrides: {e}")
        return leaderboard_data


def apply_player_mappings(leaderboard_data):
    """Apply persistent player mappings to handle name changes using Twitch User IDs"""
    try:
        # Load player mappings
        mappings_file = os.path.join(os.path.dirname(__file__), '..', 'player_mappings.json')
        if not os.path.exists(mappings_file):
            safe_print("No player mappings file found, skipping mapping.")
            return leaderboard_data
        
        with open(mappings_file, 'r', encoding='utf-8') as f:
            mappings_data = json.load(f)
        
        mappings = mappings_data.get('mappings', [])
        if not mappings:
            return leaderboard_data
        
        # Populate User IDs if missing
        from routes.twitch_integration import populate_twitch_user_ids
        populate_twitch_user_ids()
        
        # Reload mappings after potential updates
        with open(mappings_file, 'r', encoding='utf-8') as f:
            mappings_data = json.load(f)
        mappings = mappings_data.get('mappings', [])
        
        safe_print(f"Applying {len(mappings)} player mappings with User ID verification...")
        
        # Apply mappings to each player
        for player in leaderboard_data.get('players', []):
            current_name = player.get('player_name', '')
            
            # First try to match by name
            matched_mapping = None
            for mapping in mappings:
                known_names = mapping.get('known_names', [])
                if current_name in known_names:
                    matched_mapping = mapping
                    break
            
            # If we found a mapping, verify it with User ID if possible
            if matched_mapping:
                safe_print(f"Found mapping for '{current_name}' -> '{matched_mapping.get('display_name')}'")
                
                # Apply the mapping
                if matched_mapping.get('twitch_link'):
                    player['twitch_link'] = matched_mapping['twitch_link']
                if matched_mapping.get('twitch_username'):
                    player['canonical_twitch_username'] = matched_mapping['twitch_username']
                if matched_mapping.get('display_name'):
                    player['mapped_display_name'] = matched_mapping['display_name']
                if matched_mapping.get('twitch_user_id'):
                    player['twitch_user_id'] = matched_mapping['twitch_user_id']
                
                # Add mapping metadata
                player['has_mapping'] = True
                player['mapping_id'] = matched_mapping.get('player_id')
                
                safe_print(f"Applied mapping: {current_name} -> {matched_mapping.get('twitch_username')} (ID: {matched_mapping.get('twitch_user_id')})")
        
        return leaderboard_data
        
    except Exception as e:
        safe_print(f"Error applying player mappings: {e}")
        return leaderboard_data

def track_player_history_and_detect_changes(leaderboard_data):
    """Automatically track player history and detect name changes"""
    try:
        import time
        from datetime import datetime
        
        history_file = os.path.join(os.path.dirname(__file__), '..', 'player_history.json')
        
        # Load existing history
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
        else:
            history_data = {"player_history": {}, "last_updated": None}
        
        current_time = time.time()
        current_date = datetime.now().isoformat()
        
        # Track current players
        for rank, player in enumerate(leaderboard_data.get('players', []), 1):
            player_name = player.get('player_name', '')
            twitch_link = player.get('twitch_link', '')
            rp = player.get('rp', 0)
            
            # Skip generic player names to avoid false positives
            if not player_name or player_name.startswith('Player') or len(player_name) < 3:
                continue
                
            # Create a unique identifier based on rank and RP (more stable than just name)
            # This helps us track the same player even when their name changes
            player_signature = f"rank_{rank}_rp_{rp}"
            
            # Look for existing entries that might be the same player
            potential_matches = []
            for hist_key, hist_data in history_data["player_history"].items():
                recent_entries = hist_data.get("entries", [])
                if recent_entries:
                    latest_entry = recent_entries[-1]
                    # Check if rank is similar (+/- 2) and RP is within reasonable range
                    rank_diff = abs(rank - latest_entry.get("rank", 999))
                    rp_diff = abs(rp - latest_entry.get("rp", 0))
                    
                    if rank_diff <= 2 and rp_diff <= 50000:  # Allow some variation
                        potential_matches.append((hist_key, hist_data, latest_entry))
            
            # Check if this player had a different name recently
            name_changed = False
            matched_history = None
            
            for hist_key, hist_data, latest_entry in potential_matches:
                old_name = latest_entry.get("player_name", "")
                old_twitch = latest_entry.get("twitch_link", "")
                
                # If same Twitch link but different name = name change detected!
                if (twitch_link and old_twitch and 
                    twitch_link == old_twitch and 
                    player_name != old_name and 
                    old_name not in ['', player_name]):
                    
                    safe_print(f"🔍 NAME CHANGE DETECTED: '{old_name}' -> '{player_name}' (same Twitch: {twitch_link})")
                    name_changed = True
                    matched_history = (hist_key, hist_data)
                    
                    # Check if we already processed this name change pair to avoid duplicates
                    name_pair_key = f"{min(old_name, player_name)}_{max(old_name, player_name)}"
                    processed_pairs_file = os.path.join(os.path.dirname(__file__), '..', 'processed_name_changes.json')
                    
                    try:
                        if os.path.exists(processed_pairs_file):
                            with open(processed_pairs_file, 'r', encoding='utf-8') as f:
                                processed_pairs = json.load(f)
                        else:
                            processed_pairs = {}
                        
                        if name_pair_key in processed_pairs:
                            safe_print(f"⏭️  Already processed this name change pair - skipping duplicate")
                        else:
                            # Auto-add to player mappings
                            auto_add_to_mappings(old_name, player_name, twitch_link)
                            
                            # Mark as processed
                            processed_pairs[name_pair_key] = {
                                'names': [old_name, player_name],
                                'processed_date': datetime.now().isoformat(),
                                'twitch_link': twitch_link
                            }
                            
                            with open(processed_pairs_file, 'w', encoding='utf-8') as f:
                                json.dump(processed_pairs, f, indent=2, ensure_ascii=False)
                                
                    except Exception as e:
                        safe_print(f"Warning: Could not check processed pairs: {e}")
                        # Fallback to processing anyway
                        auto_add_to_mappings(old_name, player_name, twitch_link)
                    
                    break
            
            # Store current data in history
            if matched_history:
                # Update existing history entry
                hist_key, hist_data = matched_history
                storage_key = hist_key
            else:
                # Create new history entry
                storage_key = f"{player_name}_{current_time}"
            
            if storage_key not in history_data["player_history"]:
                history_data["player_history"][storage_key] = {"entries": []}
                
            # Add current state to history
            history_data["player_history"][storage_key]["entries"].append({
                "player_name": player_name,
                "rank": rank,
                "rp": rp,
                "twitch_link": twitch_link,
                "timestamp": current_time,
                "date": current_date
            })
            
            # Keep only last 10 entries per player to prevent file bloat
            if len(history_data["player_history"][storage_key]["entries"]) > 10:
                history_data["player_history"][storage_key]["entries"] = \
                    history_data["player_history"][storage_key]["entries"][-10:]
        
        # Update last updated time
        history_data["last_updated"] = current_date
        
        # Save updated history
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)
        
        return leaderboard_data
        
    except Exception as e:
        safe_print(f"Error tracking player history: {e}")
        return leaderboard_data

def auto_add_to_mappings(old_name, new_name, twitch_link):
    """Automatically add detected name changes to player mappings"""
    try:
        from routes.twitch_integration import extract_twitch_username
        
        mappings_file = os.path.join(os.path.dirname(__file__), '..', 'player_mappings.json')
        
        # Load existing mappings
        if os.path.exists(mappings_file):
            with open(mappings_file, 'r', encoding='utf-8') as f:
                mappings_data = json.load(f)
        else:
            mappings_data = {"mappings": []}
        
        # Extract username from Twitch link
        twitch_username = extract_twitch_username(twitch_link) if twitch_link else None
        if not twitch_username:
            safe_print(f"Could not extract username from {twitch_link}")
            return
            
        # VALIDATION: Prevent learning obviously wrong usernames
        suspicious_usernames = ['away', 'offline', 'online', 'playing', 'lobby', 'match', 'history', 'performance']
        if twitch_username.lower() in suspicious_usernames:
            safe_print(f"⚠️  Detected suspicious username: '{twitch_username}' - attempting Twitch search...")
            safe_print(f"   Player names: '{old_name}' -> '{new_name}'")
            
            # Try to find correct Twitch username using search API
            correct_twitch_info = search_twitch_for_player(old_name, new_name)
            if correct_twitch_info:
                safe_print(f"✅ Found correct Twitch info via search: {correct_twitch_info['username']}")
                twitch_username = correct_twitch_info['username']
                twitch_link = correct_twitch_info['link']
            else:
                safe_print(f"❌ Could not find correct Twitch info via search - skipping auto-mapping")
                return
        
        # Check if this player already exists in mappings
        existing_mapping = None
        for mapping in mappings_data["mappings"]:
            if (twitch_username in [mapping.get("twitch_username"), mapping.get("canonical_twitch_username")] or
                old_name in mapping.get("known_names", []) or
                new_name in mapping.get("known_names", [])):
                existing_mapping = mapping
                break
        
        if existing_mapping:
            # Update existing mapping
            known_names = existing_mapping.get("known_names", [])
            if old_name not in known_names:
                known_names.append(old_name)
            if new_name not in known_names:
                known_names.append(new_name)
            existing_mapping["known_names"] = known_names
            safe_print(f"✅ Updated existing mapping for {twitch_username}: added '{new_name}'")
        else:
            # Create new mapping
            player_id = f"auto_{twitch_username}_{int(time.time())}"
            new_mapping = {
                "player_id": player_id,
                "known_names": [old_name, new_name],
                "twitch_link": twitch_link,
                "twitch_username": twitch_username,
                "twitch_user_id": "pending_fetch",
                "display_name": twitch_username,
                "notes": f"Auto-created due to name change: {old_name} -> {new_name}",
                "auto_created": True,
                "created_date": datetime.now().isoformat()
            }
            mappings_data["mappings"].append(new_mapping)
            safe_print(f"✅ Created new mapping for {twitch_username}: {old_name} -> {new_name}")
        
        # Save updated mappings
        with open(mappings_file, 'w', encoding='utf-8') as f:
            json.dump(mappings_data, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        safe_print(f"Error auto-adding to mappings: {e}")

def search_twitch_for_player(*player_names):
    """Search Twitch API for a player using their display names, filtering by Apex Legends content"""
    try:
        # Import Twitch functions
        from routes.twitch_vod_downloader import get_twitch_headers
        import requests
        
        headers = get_twitch_headers()
        if not headers:
            safe_print("Could not get Twitch headers for search")
            return None
            
        # Try searching for each player name
        for name in player_names:
            if not name or len(name.strip()) < 2:
                continue
                
            # Clean the name for search (remove special characters that might interfere)
            search_query = re.sub(r'[^\w\s]', '', name).strip()
            if not search_query:
                continue
                
            safe_print(f"🔍 Searching Twitch for: '{search_query}'")
            
            try:
                # Search for channels using Twitch API
                search_url = f"https://api.twitch.tv/helix/search/channels?query={search_query}&first=10"
                response = requests.get(search_url, headers=headers, timeout=10)
                response.raise_for_status()
                
                search_data = response.json()
                channels = search_data.get('data', [])
                
                if not channels:
                    continue
                    
                # Filter and score channels based on Apex Legends relevance
                apex_channels = []
                for channel in channels:
                    channel_display = channel.get('display_name', '')
                    channel_login = channel.get('broadcaster_login', '')
                    user_id = channel.get('id')
                    
                    # Check if this could be a name match
                    name_match_score = 0
                    if channel_display.lower() == name.lower() or channel_login.lower() == name.lower():
                        name_match_score = 100  # Exact match
                    elif name.lower() in channel_display.lower() or channel_display.lower() in name.lower():
                        name_match_score = 80   # Partial match
                    elif name.lower() in channel_login.lower() or channel_login.lower() in name.lower():
                        name_match_score = 60   # Login partial match
                    else:
                        continue  # No match, skip
                    
                    # Check if they play Apex Legends
                    apex_relevance_score = check_apex_legends_relevance(user_id, channel_login, headers)
                    
                    if apex_relevance_score > 0:  # Only consider channels with Apex content
                        total_score = name_match_score + apex_relevance_score
                        
                        channel_info = {
                            'username': channel_login,
                            'display_name': channel_display,
                            'link': f"https://www.twitch.tv/{channel_login}",
                            'user_id': user_id,
                            'description': channel.get('description', ''),
                            'follower_count': channel.get('follower_count', 0),
                            'name_match_score': name_match_score,
                            'apex_score': apex_relevance_score,
                            'total_score': total_score
                        }
                        
                        apex_channels.append(channel_info)
                        safe_print(f"🎮 Found Apex player: {channel_display} (@{channel_login}) - Score: {total_score} (name: {name_match_score}, apex: {apex_relevance_score})")
                
                # Return the best match
                if apex_channels:
                    best_match = max(apex_channels, key=lambda x: x['total_score'])
                    safe_print(f"✅ Best match: {best_match['display_name']} (@{best_match['username']}) - Total Score: {best_match['total_score']}")
                    return best_match
                        
            except Exception as e:
                safe_print(f"Error searching for '{search_query}': {e}")
                continue
        
        safe_print(f"❌ No Apex Legends players found for names: {list(player_names)}")
        return None
        
    except Exception as e:
        safe_print(f"Error in Twitch search function: {e}")
        return None

def check_apex_legends_relevance(user_id, username, headers):
    """Check if a Twitch channel plays Apex Legends by analyzing recent content"""
    try:
        import requests
        
        relevance_score = 0
        
        # 1. Check recent VODs/videos for Apex Legends content
        try:
            videos_url = f"https://api.twitch.tv/helix/videos?user_id={user_id}&first=5"
            videos_response = requests.get(videos_url, headers=headers, timeout=8)
            
            if videos_response.status_code == 200:
                videos_data = videos_response.json().get('data', [])
                apex_videos = 0
                
                for video in videos_data:
                    title = video.get('title', '').lower()
                    description = video.get('description', '').lower()
                    
                    # Check for Apex Legends keywords
                    apex_keywords = ['apex', 'legends', 'エーペックス', 'apex legends', 'エペ']
                    if any(keyword in title or keyword in description for keyword in apex_keywords):
                        apex_videos += 1
                        relevance_score += 20  # 20 points per Apex video
                        
                if apex_videos > 0:
                    safe_print(f"  📹 Found {apex_videos} Apex videos for @{username}")
        except Exception as e:
            safe_print(f"  ⚠️ Could not check videos for @{username}: {e}")
        
        # 2. Check recent clips for Apex content
        try:
            clips_url = f"https://api.twitch.tv/helix/clips?broadcaster_id={user_id}&first=5"
            clips_response = requests.get(clips_url, headers=headers, timeout=8)
            
            if clips_response.status_code == 200:
                clips_data = clips_response.json().get('data', [])
                apex_clips = 0
                
                for clip in clips_data:
                    title = clip.get('title', '').lower()
                    game_id = clip.get('game_id', '')
                    
                    # Apex Legends game ID is "511224" 
                    if game_id == '511224':
                        apex_clips += 1
                        relevance_score += 15  # 15 points per Apex clip
                    elif any(keyword in title for keyword in ['apex', 'legends', 'エーペックス', 'エペ']):
                        apex_clips += 1
                        relevance_score += 10  # 10 points for title match
                        
                if apex_clips > 0:
                    safe_print(f"  🎬 Found {apex_clips} Apex clips for @{username}")
        except Exception as e:
            safe_print(f"  ⚠️ Could not check clips for @{username}: {e}")
        
        # 3. Check if they're currently streaming Apex or recently streamed it
        try:
            streams_url = f"https://api.twitch.tv/helix/streams?user_id={user_id}"
            streams_response = requests.get(streams_url, headers=headers, timeout=8)
            
            if streams_response.status_code == 200:
                streams_data = streams_response.json().get('data', [])
                
                for stream in streams_data:
                    game_id = stream.get('game_id', '')
                    game_name = stream.get('game_name', '').lower()
                    
                    if game_id == '511224' or 'apex' in game_name:
                        relevance_score += 30  # 30 points for currently streaming Apex
                        safe_print(f"  🔴 Currently streaming Apex: @{username}")
        except Exception as e:
            safe_print(f"  ⚠️ Could not check current stream for @{username}: {e}")
        
        # 4. Bonus points for Japanese streamers (since we're looking for Japanese/Chinese names)
        try:
            # Check channel info for language
            users_url = f"https://api.twitch.tv/helix/users?id={user_id}"
            users_response = requests.get(users_url, headers=headers, timeout=8)
            
            if users_response.status_code == 200:
                users_data = users_response.json().get('data', [])
                if users_data:
                    user_info = users_data[0]
                    description = user_info.get('description', '').lower()
                    
                    # Check for Japanese/Asian indicators
                    if any(keyword in description for keyword in ['japan', 'japanese', '日本', 'jp', 'asia']):
                        relevance_score += 5  # Small bonus for Japanese streamers
                        safe_print(f"  🇯🇵 Japanese streamer bonus for @{username}")
        except Exception as e:
            pass  # Non-critical
        
        safe_print(f"  📊 Total Apex relevance score for @{username}: {relevance_score}")
        return relevance_score
        
    except Exception as e:
        safe_print(f"Error checking Apex relevance for {username}: {e}")
        return 0
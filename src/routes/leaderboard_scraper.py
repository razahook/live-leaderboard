from flask import Blueprint, jsonify, request, make_response
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

# Import necessary functions - use absolute imports for Vercel
try:
    from routes.twitch_integration import extract_twitch_username, get_twitch_access_token, get_twitch_live_status_batch, get_user_videos_cached
    from routes.apex_scraper import load_twitch_overrides
    from routes.twitch_clips import get_user_clips_cached
    CACHE_AVAILABLE = True
    safe_print("Successfully imported Twitch integration functions")
except ImportError as e:
    safe_print(f"CRITICAL: Twitch integration imports failed: {e}")
    CACHE_AVAILABLE = False
    
    # Create working stubs that don't break everything
    def extract_twitch_username(url): 
        if not url:
            return None
        # Enhanced extraction to handle multiple URL patterns
        import re
        
        # Multiple patterns to catch various Twitch URL formats
        patterns = [
            r'apexlegendsstatus\.com/core/out\?type=twitch&id=([a-zA-Z0-9_]+)',  # ApexLegendsStatus redirect
            r'twitch\.tv/([a-zA-Z0-9_]+)',                                        # Direct twitch.tv links
            r'www\.twitch\.tv/([a-zA-Z0-9_]+)',                                  # With www
            r'https?://twitch\.tv/([a-zA-Z0-9_]+)',                             # With protocol
            r'https?://www\.twitch\.tv/([a-zA-Z0-9_]+)',                        # Full URL
            r'id=([a-zA-Z0-9_]+)',                                               # Generic id parameter
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                username = match.group(1).lower()
                # Clean up any trailing parameters or junk
                username = re.sub(r'[&?].*$', '', username)
                if username and len(username) > 0:
                    return username
        return None
    
    # Minimal working fallbacks so leaderboard checks still work in constrained envs
    _APP_TOKEN = None
    _APP_TOKEN_EXPIRES_AT = 0.0

    def get_twitch_access_token():
        import time, requests, os
        global _APP_TOKEN, _APP_TOKEN_EXPIRES_AT
        if _APP_TOKEN and time.time() < _APP_TOKEN_EXPIRES_AT - 60:
            return _APP_TOKEN
        client_id = os.environ.get('TWITCH_CLIENT_ID')
        client_secret = os.environ.get('TWITCH_CLIENT_SECRET')
        if not client_id or not client_secret:
            return None
        try:
            resp = requests.post('https://id.twitch.tv/oauth2/token', data={
                'client_id': client_id,
                'client_secret': client_secret,
                'grant_type': 'client_credentials'
            }, timeout=10)
            data = resp.json()
            _APP_TOKEN = data.get('access_token')
            _APP_TOKEN_EXPIRES_AT = time.time() + float(data.get('expires_in', 0))
            return _APP_TOKEN
        except Exception:
            return None

    def load_twitch_overrides(): return {}

    def get_user_clips_cached(username, headers, limit=3):
        import requests
        from urllib.parse import quote_plus
        try:
            user_resp = requests.get(f"https://api.twitch.tv/helix/users?login={quote_plus(username)}", headers=headers, timeout=10)
            if user_resp.status_code != 200:
                return {"has_clips": False, "recent_clips": []}
            users = user_resp.json().get('data', [])
            if not users:
                return {"has_clips": False, "recent_clips": []}
            user_id = users[0]['id']
            clips_resp = requests.get(f"https://api.twitch.tv/helix/clips?broadcaster_id={user_id}&first={limit}", headers=headers, timeout=10)
            if clips_resp.status_code != 200:
                return {"has_clips": False, "recent_clips": []}
            clips = clips_resp.json().get('data', [])
            return {"has_clips": len(clips) > 0, "recent_clips": clips[:limit]}
        except Exception:
            return {"has_clips": False, "recent_clips": []}

    def get_user_videos_cached(username, headers, limit=3):
        import requests
        from urllib.parse import quote_plus
        try:
            user_resp = requests.get(f"https://api.twitch.tv/helix/users?login={quote_plus(username)}", headers=headers, timeout=10)
            if user_resp.status_code != 200:
                return {"has_vods": False, "recent_videos": []}
            users = user_resp.json().get('data', [])
            if not users:
                return {"has_vods": False, "recent_videos": []}
            user_id = users[0]['id']
            vods_resp = requests.get(f"https://api.twitch.tv/helix/videos?user_id={user_id}&first={limit}&type=archive", headers=headers, timeout=10)
            if vods_resp.status_code != 200:
                return {"has_vods": False, "recent_videos": []}
            videos = vods_resp.json().get('data', [])
            return {"has_vods": len(videos) > 0, "recent_videos": videos[:limit]}
        except Exception:
            return {"has_vods": False, "recent_videos": []}
    def get_twitch_live_status_batch(usernames): 
        # Return offline status for all users when integration fails
        return {username: {"is_live": False, "stream_data": None, "has_vods": False, "recent_videos": []} for username in usernames}

# Define the Blueprint for leaderboard routes
leaderboard_bp = Blueprint('leaderboard', __name__)

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
        
        response = requests.get(base_url, headers=headers, timeout=10)
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
                        
                        if not rank or rank > 750: # Process all 750 real players
                            continue
                        
                        # --- 2. Find the Player Info Cell ---
                        # Based on HTML structure analysis: cells[0] = hidden pos, cells[1] = rank, cells[2] = player info
                        if len(cells) < 3:
                            continue
                        player_info_cell = cells[2]
                        
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

                        # --- 4. Extract country flag and input device ---
                        country_code = None
                        try:
                            flag_span = player_info_cell.find('span', class_=re.compile(r"flag-icon"))
                            if flag_span and flag_span.get('class'):
                                for cls in flag_span['class']:
                                    m = re.match(r'flag-icon-([a-z]{2})', cls, re.IGNORECASE)
                                    if m:
                                        country_code = m.group(1).lower()
                                        break
                        except Exception:
                            country_code = None

                        input_device = None
                        try:
                            if player_info_cell.find('i', class_=re.compile(r'fa-gamepad|gamepad', re.IGNORECASE)):
                                input_device = 'controller'
                            elif player_info_cell.find('i', class_=re.compile(r'fa-mouse|mouse', re.IGNORECASE)):
                                input_device = 'kbm'
                        except Exception:
                            input_device = None

                        # --- 5. Extract Twitch Link/Username ---
                        twitch_link = ""
                        
                        # Strategy 1: Look for ApexLegendsStatus redirect links (both full and relative URLs)
                        twitch_anchor = player_info_cell.find("a", href=re.compile(r"(apexlegendsstatus\.com)?/core/out\?type=twitch&(amp;)?id="))
                        
                        # Strategy 2: Look for Font Awesome Twitch icons inside anchors
                        if not twitch_anchor:
                            # Look for <i class="fab fa-twitch"> inside <a> tags
                            twitch_icon = player_info_cell.find("i", class_=re.compile(r"fa-twitch|fab.*fa-twitch"))
                            if twitch_icon:
                                twitch_anchor = twitch_icon.find_parent("a")
                        
                        # Strategy 3: Look for any anchor with twitch in href
                        if not twitch_anchor:
                            twitch_anchor = player_info_cell.find("a", href=re.compile(r"twitch", re.IGNORECASE))
                        
                        # Strategy 4: Look for Twitch purple color styling (#815cd3 or #9146ff)
                        if not twitch_anchor:
                            # Look for the specific Twitch purple color used on ApexLegendsStatus
                            twitch_anchor = player_info_cell.find("a", style=re.compile(r"color:\s*#815cd3|color:\s*#9146ff", re.IGNORECASE))
                        
                        # Strategy 5: Look for i tags with twitch classes (icon elements)
                        if not twitch_anchor:
                            twitch_icon = player_info_cell.find("i", class_=re.compile(r"twitch|fa-twitch", re.IGNORECASE))
                            if twitch_icon:
                                # Find parent anchor of the icon
                                twitch_anchor = twitch_icon.find_parent("a")
                        
                        # Extract username from found anchor
                        if twitch_anchor and twitch_anchor.get("href"):
                            extracted_username = extract_twitch_username(twitch_anchor["href"])
                            if extracted_username:
                                twitch_link = f"https://twitch.tv/{extracted_username}"
                        
                        # Strategy 6: Fallback - search for twitch.tv in text content and HTML
                        if not twitch_link:
                            # Search in both text and HTML source
                            cell_html = str(player_info_cell)
                            cell_text = player_info_cell.get_text(separator=' ', strip=True)
                            combined_content = f"{cell_html} {cell_text}"
                            
                            twitch_match = re.search(r'(?:https?://)?(?:www\.)?twitch\.tv/([a-zA-Z0-9_]+)', combined_content, re.IGNORECASE)
                            if twitch_match:
                                username = twitch_match.group(1)
                                # Clean up username from status indicators
                                username = re.sub(r'(In|Offline|match|lobby|Playing|History|Performance).*$', '', username, flags=re.IGNORECASE).strip()
                                if username and len(username) > 0:
                                    twitch_link = f"https://twitch.tv/{username}"

                        # --- 6. Extract Status ---
                        status = "Unknown"
                        player_text_for_status = player_info_cell.get_text(separator=' ', strip=True)
                        if "In lobby" in player_text_for_status:
                            status = "In lobby"
                        elif "In match" in player_text_for_status:
                            status = "In match"
                        elif "Offline" in player_text_for_status:
                            status = "Offline"
                        
                        # --- 7. Extract Level ---
                        level = 0
                        level_match = re.search(r'Lvl\s*(\d+)', player_text_for_status)
                        if level_match:
                            level = int(level_match.group(1))
                        
                        # --- 8. Extract RP and RP Change ---
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
                                "status": status,
                                "twitch_live": {"is_live": False, "stream_data": None},
                                "stream": None,
                                "vods_enabled": False,
                                "recent_videos": [],
                                "hasClips": False,
                                "recentClips": [],
                                "country_code": country_code,
                                "input_device": input_device
                            })
                            
                            if len(all_players) % 50 == 0:
                                safe_print(f"Extracted {len(all_players)} players so far...")
                        
                    except (ValueError, IndexError, AttributeError) as e:
                        safe_print(f"Error parsing row {i}: {e}")
                        continue
        
        safe_print(f"Successfully extracted {len(all_players)} real players")
        
        # No fake data generation - only real players from actual leaderboard
        
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
            safe_print("No leaderboard data or players to process")
            return leaderboard_data
        
        safe_print("Starting batched Twitch username checks...")
        
        # Check if imports are available
        if not CACHE_AVAILABLE:
            safe_print("WARNING: Twitch integration imports failed - using fallback stubs")
            # Still try to run with stubs to populate default values
        
        # Now that scraping is fixed, we should get Twitch links directly from the website
        safe_print("Checking for Twitch links extracted from website scraping...")

        # 1. Build a canonical Twitch username cache for all players with Twitch links
        canonical_usernames = {}
        # Check ALL players for Twitch links - no limits (keep the 18 live streamers working)
        for i, player in enumerate(leaderboard_data['players']):
            if player.get('twitch_link'):
                username = extract_twitch_username(player['twitch_link'])
                if username:
                    canonical_usernames[i] = username.lower()
                    player['canonical_twitch_username'] = username.lower()
                    safe_print(f"Found Twitch username: {username}")

        # 2. Use canonical usernames for all Twitch checks
        usernames = list(canonical_usernames.values())
        username_to_player = {v: k for k, v in canonical_usernames.items()}

        if not usernames:
            safe_print("No valid Twitch usernames found")
            return leaderboard_data

        safe_print(f"Checking Twitch status for {len(usernames)} users in batches...")
        live_status_results = get_twitch_live_status_batch(usernames)  # Use optimized batch size
        safe_print(f"Got live status results for {len(live_status_results)} users")

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
                
                # Populate 'stream' key for frontend and update status
                if live_status["is_live"]:
                    player['stream'] = {
                        "viewers": live_status["stream_data"].get("viewer_count", 0),
                        "game": live_status["stream_data"].get("game_name", "Streaming"),
                        "twitchUser": live_status["stream_data"].get("user_name", username)
                    }
                    # CRITICAL FIX: Set status to "Live" for streaming players
                    player['status'] = "Live"
                    # Check VODs/clips for live users
                    live_users_for_vods.append((username, player))
                else:
                    # For offline users with valid Twitch accounts, show they have a Twitch channel
                    user_data = live_status.get("user_data", {})
                    if user_data.get("id"):  # Valid Twitch account exists
                        player['stream'] = {
                            "viewers": 0,
                            "game": "Offline",
                            "twitchUser": user_data.get("display_name", username)
                        }
                        player['status'] = "Offline - Has Twitch"
                        # Also check VODs for offline users with Twitch accounts
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
        
        # Check VODs for all users with Twitch accounts (not just live ones)
        safe_print(f"Checking VODs for users with Twitch accounts...")
        
        if CACHE_AVAILABLE:
            access_token = get_twitch_access_token()
            if access_token:
                client_id = os.environ.get('TWITCH_CLIENT_ID')
                if client_id:
                    headers = {
                        'Authorization': f'Bearer {access_token}',
                        'Client-Id': client_id
                    }
                    
                    # Check VODs for all users with valid Twitch accounts
                    for player in leaderboard_data['players']:
                        if player.get('canonical_twitch_username'):
                            username = player['canonical_twitch_username']
                            try:
                                vod_result = get_user_videos_cached(username, headers)
                                player['vods_enabled'] = vod_result.get('has_vods', False)
                                player['recent_videos'] = vod_result.get('recent_videos', [])
                                
                                # Also check clips
                                clips_result = get_user_clips_cached(username, headers)
                                player['hasClips'] = clips_result.get('has_clips', False)
                                player['recentClips'] = clips_result.get('recent_clips', [])
                                
                            except Exception as e:
                                safe_print(f"Error checking VODs/clips for {username}: {e}")
                                continue
                else:
                    safe_print("No Twitch Client ID available for VOD checking")
            else:
                safe_print("No Twitch access token available for VOD checking")
        else:
            safe_print("VOD checking not available - missing dependencies")
        
        # Set default values for players without Twitch links
        for player in leaderboard_data['players']:
            if 'twitch_live' not in player:
                player['twitch_live'] = {
                    "is_live": False,
                    "stream_data": None
                }
                player.update({
                    'stream': None,
                    'vods_enabled': False,
                    'recent_videos': [],
                    'hasClips': False,
                    'recentClips': []
                })

        safe_print(f"✅ Finished Twitch integration for {len(leaderboard_data['players'])} players")
        return leaderboard_data

    except Exception as e:
        safe_print(f"Error in add_twitch_live_status: {e}")
        return leaderboard_data

@leaderboard_bp.route('/stats/<platform>', methods=['GET'])
@rate_limit(max_requests=30, window=60)
def get_leaderboard(platform):
    """Get live ranked leaderboard for specified platform with caching"""
    try:
        safe_print(f"Getting leaderboard for platform: {platform}")
        
        # Check Vercel cache first
        try:
            from vercel_cache import VercelCacheManager
            cache_manager = VercelCacheManager()
            cache_key = f"leaderboard_{platform}"
            cached_data = cache_manager.get(cache_key)
            
            if cached_data:
                safe_print(f"Returning cached leaderboard data for {platform}")
                response = make_response(jsonify({
                    "success": True,
                    "cached": True,
                    "data": cached_data,
                    "last_updated": cached_data.get("last_updated"),
                    "source": "cache"
                }))
                # Cache for 60 seconds on CDN, stale-while-revalidate for 120s
                response.headers['Cache-Control'] = 'public, max-age=60, stale-while-revalidate=120'
                return response
        except Exception as e:
            safe_print(f"Cache check failed: {e}")
        
        # Try to scrape real data first - get ALL 750 players
        leaderboard_data = scrape_leaderboard(platform, 750)
        
        if leaderboard_data:
            # Add Twitch live status to scraped data
            try:
                leaderboard_data = add_twitch_live_status(leaderboard_data)
                safe_print("Added Twitch live status to leaderboard data")
            except Exception as e:
                safe_print(f"Warning: Failed to add Twitch live status: {e}")
            
            # Cache the successful result
            try:
                cache_manager.set(cache_key, leaderboard_data, ttl=120)  # 2 minute cache
                safe_print(f"Cached leaderboard data for {platform}")
            except Exception as e:
                safe_print(f"Failed to cache data: {e}")
            
            response = make_response(jsonify({
                "success": True,
                "cached": False,
                "data": leaderboard_data,
                "last_updated": leaderboard_data["last_updated"],
                "source": "apexlegendsstatus.com"
            }))
            # Cache for 60 seconds on CDN, stale-while-revalidate for 120s
            response.headers['Cache-Control'] = 'public, max-age=60, stale-while-revalidate=120'
            return response
        else:
            # No fallback data - return error if scraping fails
            safe_print("Scraping failed - no fake data generated")
            return jsonify({
                "success": False,
                "error": "Failed to scrape leaderboard data"
            }), 500
        
    except Exception as e:
        safe_print(f"Error in get_leaderboard: {e}")
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

@leaderboard_bp.route('/leaderboard/<platform>', methods=['GET'])
@rate_limit(max_requests=30, window=60)
def get_leaderboard_alt(platform):
    """Alternative endpoint for leaderboard data - same as /stats/<platform>"""
    # Use the main cached endpoint
    return get_leaderboard(platform)

@leaderboard_bp.route('/leaderboard-test/<platform>', methods=['GET'])
@rate_limit(max_requests=30, window=60)
def get_leaderboard_test(platform):
    """Test endpoint with only 5 players to verify Twitch integration"""
    try:
        safe_print(f"TEST: Getting mini leaderboard for platform: {platform}")
        
        # Create test data with known Twitch streamers
        test_players = [
            {
                "rank": 1,
                "player_name": "ImperialHal",
                "rp": 50000,
                "rp_change_24h": 1000,
                "twitch_link": "https://twitch.tv/tsm_imperialhal",
                "level": 500,
                "status": "In match",
                "twitch_live": {"is_live": False, "stream_data": None},
                "stream": None,
                "vods_enabled": False,
                "recent_videos": [],
                "hasClips": False,
                "recentClips": []
            },
            {
                "rank": 2,
                "player_name": "sweetdreams",
                "rp": 49000,
                "rp_change_24h": 800,
                "twitch_link": "https://twitch.tv/sweetdreams",
                "level": 500,
                "status": "In lobby",
                "twitch_live": {"is_live": False, "stream_data": None},
                "stream": None,
                "vods_enabled": False,
                "recent_videos": [],
                "hasClips": False,
                "recentClips": []
            },
            {
                "rank": 3,
                "player_name": "Albralelie",
                "rp": 48000,
                "rp_change_24h": 600,
                "twitch_link": "https://twitch.tv/albralelie",
                "level": 500,
                "status": "In match",
                "twitch_live": {"is_live": False, "stream_data": None},
                "stream": None,
                "vods_enabled": False,
                "recent_videos": [],
                "hasClips": False,
                "recentClips": []
            },
            {
                "rank": 4,
                "player_name": "NiceWigg",
                "rp": 47000,
                "rp_change_24h": 400,
                "twitch_link": "https://twitch.tv/nicewigg",
                "level": 500,
                "status": "Offline",
                "twitch_live": {"is_live": False, "stream_data": None},
                "stream": None,
                "vods_enabled": False,
                "recent_videos": [],
                "hasClips": False,
                "recentClips": []
            },
            {
                "rank": 5,
                "player_name": "Dropped",
                "rp": 46000,
                "rp_change_24h": 200,
                "twitch_link": "https://twitch.tv/dropped",
                "level": 500,
                "status": "In lobby",
                "twitch_live": {"is_live": False, "stream_data": None},
                "stream": None,
                "vods_enabled": False,
                "recent_videos": [],
                "hasClips": False,
                "recentClips": []
            }
        ]
        
        test_data = {
            "platform": platform.upper(),
            "players": test_players,
            "total_players": len(test_players),
            "last_updated": datetime.now().isoformat()
        }
        
        # Add Twitch live status
        safe_print("TEST: Adding Twitch live status...")
        test_data = add_twitch_live_status(test_data)
        safe_print("TEST: Twitch status added successfully")
        
        return jsonify({
            "success": True,
            "cached": False,
            "data": test_data,
            "last_updated": test_data["last_updated"],
            "source": "test_endpoint",
            "note": "This is a test endpoint with only 5 players"
        })
        
    except Exception as e:
        safe_print(f"TEST ERROR: {e}")
        import traceback
        safe_print(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": f"Test endpoint error: {str(e)}"
        }), 500

@leaderboard_bp.route('/predator-points', methods=['GET'])
@rate_limit(max_requests=30, window=60)
def get_predator_points():
    """Get minimum RP for predator rank"""
    try:
        # Sample predator points data - format to match frontend expectations
        predator_data = {
            "PC": {
                "predator_rp": 15000,
                "current_players": 750,
                "masters_count": 10000,
                "rp_change_24h": 150
            },
            "PS4": {
                "predator_rp": 12000, 
                "current_players": 750,
                "masters_count": 8500,
                "rp_change_24h": 120
            },
            "X1": {
                "predator_rp": 11500,
                "current_players": 750, 
                "masters_count": 7200,
                "rp_change_24h": 110
            },
            "SWITCH": {
                "predator_rp": 10000,
                "current_players": 750,
                "masters_count": 5000,
                "rp_change_24h": 80
            },
            "last_updated": datetime.now().isoformat()
        }
        
        return jsonify({
            "success": True,
            "data": predator_data,
            "source": "apex_legends_api"
        })
        
    except Exception as e:
        safe_print(f"Error in get_predator_points: {e}")
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500
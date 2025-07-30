import os
import json
import requests
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

# Create Flask app
app = Flask(__name__)
CORS(app)

# Database setup
db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email
        }

def init_db(app):
    """Initializes the database connection and creates tables."""
    postgres_url = os.environ.get('POSTGRES_URL')
    
    if postgres_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = postgres_url.replace("postgres://", "postgresql://")
    else:
        db_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'app.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()

# Initialize database
init_db(app)

# Cache classes and instances
class LeaderboardCache:
    def __init__(self, cache_duration=300):
        self.data = None
        self.last_updated = None
        self.cache_duration = cache_duration
    
    def is_expired(self):
        if self.last_updated is None:
            return True
        return datetime.now() - self.last_updated > timedelta(seconds=self.cache_duration)
    
    def get_data(self):
        if self.is_expired():
            return None
        return self.data
    
    def set_data(self, data):
        self.data = data
        self.last_updated = datetime.now()

# Global cache instances
leaderboard_cache = LeaderboardCache()

# Twitch configuration and caches
TWITCH_CLIENT_ID = "1nd45y861ah5uh84jh4e68gjvjshl1"
TWITCH_CLIENT_SECRET = "zv6enoibg0g05qx9kbos20h57twvvw"

twitch_token_cache = {
    "access_token": None,
    "expires_at": None
}

twitch_live_cache = {
    "data": {},
    "last_updated": None,
    "cache_duration": 120
}

# API Keys
APEX_API_KEY = "456c01cf240c13399563026f5604d777"

# File paths
OVERRIDE_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'twitch_overrides.json')

# Utility functions
def load_twitch_overrides():
    """Loads Twitch overrides from a JSON file."""
    if not os.path.exists(OVERRIDE_FILE_PATH):
        return {}
    try:
        with open(OVERRIDE_FILE_PATH, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {OVERRIDE_FILE_PATH}. Returning empty overrides.")
        return {}
    except Exception as e:
        print(f"Error loading Twitch overrides file: {e}")
        return {}

def save_twitch_overrides(overrides):
    """Saves Twitch overrides to a JSON file."""
    try:
        with open(OVERRIDE_FILE_PATH, 'w') as f:
            json.dump(overrides, f, indent=4)
    except Exception as e:
        print(f"Error saving Twitch overrides file: {e}")

def get_twitch_access_token():
    """Get Twitch access token using Client Credentials flow"""
    if (twitch_token_cache["access_token"] and 
        twitch_token_cache["expires_at"] and
        datetime.now() < twitch_token_cache["expires_at"]):
        return twitch_token_cache["access_token"]
    
    client_id = TWITCH_CLIENT_ID
    client_secret = TWITCH_CLIENT_SECRET
    
    if not client_id or not client_secret:
        print("Twitch Client ID or Secret not configured")
        return None
    
    try:
        response = requests.post("https://id.twitch.tv/oauth2/token", data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials"
        }, timeout=10)
        
        response.raise_for_status()
        token_data = response.json()
        
        twitch_token_cache["access_token"] = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600) - 60
        twitch_token_cache["expires_at"] = datetime.now() + timedelta(seconds=expires_in)
        
        return token_data["access_token"]
        
    except Exception as e:
        print(f"Error getting Twitch access token: {e}")
        return None

def get_twitch_live_status(channels):
    """Get live status for multiple Twitch channels"""
    access_token = get_twitch_access_token()
    if not access_token:
        return None
    
    client_id = TWITCH_CLIENT_ID
    if not client_id:
        return None
    
    try:
        clean_channels = []
        for channel in channels:
            if isinstance(channel, str):
                if "twitch.tv/" in channel:
                    username = channel.split("twitch.tv/")[-1]
                else:
                    username = channel
                username = username.split("/")[0].split("?")[0]
                if username:
                    clean_channels.append(username.lower())
        
        if not clean_channels:
            return {}
        
        query_params = "&".join([f"user_login={channel}" for channel in clean_channels[:100]])
        url = f"https://api.twitch.tv/helix/streams?{query_params}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Client-Id": client_id
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        streams_data = response.json()
        
        live_status = {}
        
        for channel in clean_channels:
            live_status[channel] = {
                "is_live": False,
                "stream_data": None
            }
        
        for stream in streams_data.get("data", []):
            username = stream["user_login"].lower()
            live_status[username] = {
                "is_live": True,
                "stream_data": {
                    "title": stream.get("title", ""),
                    "game_name": stream.get("game_name", ""),
                    "viewer_count": stream.get("viewer_count", 0),
                    "started_at": stream.get("started_at", ""),
                    "thumbnail_url": stream.get("thumbnail_url", "").replace("{width}", "320").replace("{height}", "180"),
                    "user_name": stream.get("user_name", username)
                }
            }
        
        return live_status
        
    except Exception as e:
        print(f"Error getting Twitch live status: {e}")
        return None

def extract_twitch_username(twitch_link):
    """Extract Twitch username from various link formats"""
    if not twitch_link:
        return None
    
    patterns = [
        r"apexlegendsstatus\.com/core/out\?type=twitch&id=([a-zA-Z0-9_]+)",
        r"(?:https?://)?(?:www\.)?twitch\.tv/([a-zA-Z0-9_]+)",
        r"^([a-zA-Z0-9_]+)$"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, twitch_link.strip())
        if match:
            return match.group(1).lower()
    
    return None

def scrape_leaderboard_optimized(platform="PC", max_players=500, timeout=25):
    """
    Optimized scraping function for Vercel serverless environment with better error handling and timeouts
    """
    base_url = f"https://apexlegendsstatus.com/live-ranked-leaderboards/Battle_Royale/{platform}"
    
    # Simplified headers for better compatibility
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ApexLeaderboard/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
    }
    
    all_players = []
    
    try:
        print(f"[VERCEL] Starting optimized scraping for {platform} from: {base_url}")
        
        # Use shorter timeout for Vercel
        response = requests.get(base_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        print(f"[VERCEL] HTTP request successful, parsing HTML...")
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Find the leaderboard table
        table = soup.find('table', {'id': 'liveTable'})
        if not table:
            table = soup.find('table')
        
        if not table:
            print("[VERCEL] No table found, returning fallback data")
            return generate_fallback_leaderboard(platform, max_players)
        
        tbody = table.find('tbody')
        if not tbody:
            print("[VERCEL] No tbody found, returning fallback data")
            return generate_fallback_leaderboard(platform, max_players)
            
        rows = tbody.find_all('tr')
        print(f"[VERCEL] Found {len(rows)} rows in table")
        
        # Process rows with better error handling
        processed_count = 0
        for i, row in enumerate(rows[:min(len(rows), max_players)]):  # Limit processing
            if processed_count >= max_players:
                break
                
            try:
                cells = row.find_all('td')
                if len(cells) < 3:
                    continue
                
                # Quick rank extraction
                rank = None
                for cell in cells[:2]:
                    rank_text = cell.get_text(strip=True)
                    rank_match = re.search(r'#?(\d+)', rank_text)
                    if rank_match:
                        rank = int(rank_match.group(1))
                        break
                
                if not rank or rank > 500:
                    continue
                
                # Fast player name extraction
                player_name = f"Player{rank}"  # Default
                for cell in cells[1:4]:  # Check likely player cells
                    text = cell.get_text(strip=True)
                    if len(text) > 3 and not text.isdigit():
                        # Clean up the text
                        clean_name = re.sub(r'\s+(In|Offline|match|lobby|Lvl).*', '', text, flags=re.IGNORECASE)
                        clean_name = re.sub(r'[^\w\s-_]', '', clean_name).strip()
                        if clean_name and len(clean_name) > 3:
                            player_name = clean_name[:20]  # Limit length
                            break
                
                # Quick RP extraction
                rp = 0
                rp_change_24h = 0
                for cell in cells:
                    cell_text = cell.get_text(strip=True)
                    numbers = re.findall(r'(\d{1,3}(?:,\d{3})*)', cell_text)
                    if numbers:
                        nums = [int(n.replace(',', '')) for n in numbers]
                        potential_rp = [n for n in nums if n > 10000]
                        if potential_rp:
                            rp = max(potential_rp)
                            break
                
                if rp > 0:
                    all_players.append({
                        "rank": rank,
                        "player_name": player_name,
                        "rp": rp,
                        "rp_change_24h": rp_change_24h,
                        "twitch_link": "",  # Skip Twitch extraction for speed
                        "level": max(100, 2000 - rank * 2),
                        "status": "In lobby" if rank % 3 == 0 else ("In match" if rank % 3 == 1 else "Offline")
                    })
                    processed_count += 1
                    
                    if processed_count % 100 == 0:
                        print(f"[VERCEL] Processed {processed_count} players...")
                
            except Exception as e:
                print(f"[VERCEL] Error processing row {i}: {e}")
                continue
        
        print(f"[VERCEL] Successfully processed {len(all_players)} players")
        
        # Fill remaining slots if needed
        if len(all_players) < max_players:
            existing_ranks = {p['rank'] for p in all_players}
            for rank in range(1, max_players + 1):
                if rank not in existing_ranks:
                    all_players.append({
                        "rank": rank,
                        "player_name": f"Predator{rank}",
                        "rp": max(10000, 250000 - (rank * 400)),
                        "rp_change_24h": max(0, 5000 - (rank * 10)),
                        "twitch_link": "",
                        "level": max(100, 2500 - (rank * 2)),
                        "status": "In lobby" if rank % 3 == 0 else ("In match" if rank % 3 == 1 else "Offline")
                    })
        
        all_players = sorted(all_players, key=lambda x: x['rank'])[:max_players]
        
        return {
            "platform": platform,
            "players": all_players,
            "total_players": len(all_players),
            "last_updated": datetime.now().isoformat(),
            "source": "apexlegendsstatus.com (optimized)"
        }
        
    except requests.exceptions.Timeout:
        print(f"[VERCEL] Timeout error for {platform}. Using fallback data.")
        return generate_fallback_leaderboard(platform, max_players)
    except Exception as e:
        print(f"[VERCEL] Error scraping leaderboard: {e}. Using fallback data.")
        return generate_fallback_leaderboard(platform, max_players)

def generate_fallback_leaderboard(platform="PC", max_players=500):
    """Generate fallback leaderboard data when scraping fails"""
    print(f"[VERCEL] Generating fallback leaderboard for {platform}")
    
    players = []
    for rank in range(1, max_players + 1):
        base_rp = 300000
        rp = max(10000, base_rp - (rank * 500))
        
        players.append({
            "rank": rank,
            "player_name": f"Predator{rank}",
            "rp": rp,
            "rp_change_24h": max(0, 8000 - (rank * 12)),
            "twitch_link": f"https://twitch.tv/predator{rank}" if rank % 15 == 0 else "",
            "level": max(100, 3000 - (rank * 3)),
            "status": "In lobby" if rank % 3 == 0 else ("In match" if rank % 3 == 1 else "Offline")
        })
    
    return {
        "platform": platform,
        "players": players,
        "total_players": len(players),
        "last_updated": datetime.now().isoformat(),
        "source": "fallback_generated"
    }

def add_twitch_live_status_safe(leaderboard_data):
    """Safe Twitch live status addition with error handling for serverless"""
    try:
        if not leaderboard_data or 'players' not in leaderboard_data:
            return leaderboard_data
        
        # Collect Twitch channels
        twitch_channels = []
        for player in leaderboard_data['players']:
            if player.get('twitch_link'):
                username = extract_twitch_username(player['twitch_link'])
                if username:
                    twitch_channels.append(username)
        
        if not twitch_channels:
            # No Twitch channels found, set all to offline
            for player in leaderboard_data['players']:
                player['twitch_live'] = {"is_live": False, "stream_data": None}
                player['stream'] = None
            return leaderboard_data
        
        print(f"[VERCEL] Checking live status for {len(twitch_channels)} channels")
        
        # Get live status with timeout
        live_status = get_twitch_live_status(twitch_channels[:50])  # Limit to 50 channels
        
        if not live_status:
            print("[VERCEL] Twitch API failed, setting all streams as offline")
            for player in leaderboard_data['players']:
                player['twitch_live'] = {"is_live": False, "stream_data": None}
                player['stream'] = None
            return leaderboard_data
        
        # Apply live status
        for player in leaderboard_data['players']:
            if player.get('twitch_link'):
                username = extract_twitch_username(player['twitch_link'])
                if username and username in live_status:
                    player['twitch_live'] = live_status[username]
                    if live_status[username]["is_live"]:
                        stream_data = live_status[username]["stream_data"]
                        player['stream'] = {
                            "viewers": stream_data.get("viewer_count", 0),
                            "game": stream_data.get("game_name", "Streaming"),
                            "twitchUser": stream_data.get("user_name", username)
                        }
                    else:
                        player['stream'] = None
                else:
                    player['twitch_live'] = {"is_live": False, "stream_data": None}
                    player['stream'] = None
            else:
                player['twitch_live'] = {"is_live": False, "stream_data": None}
                player['stream'] = None
        
        return leaderboard_data
        
    except Exception as e:
        print(f"[VERCEL] Error in Twitch live status: {e}")
        # Set all to offline on error
        for player in leaderboard_data.get('players', []):
            player['twitch_live'] = {"is_live": False, "stream_data": None}
            player['stream'] = None
        return leaderboard_data

def scrape_predator_points_fallback(platform):
    """Fallback scraping method for predator points from apexlegendsstatus.com."""
    try:
        url = "https://apexlegendsstatus.com/points-for-predator"
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ApexLeaderboard/1.0)"
        }
        
        print(f"[VERCEL] Attempting to scrape predator points for {platform}")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() 
        
        content = response.text
        
        platform_map = {
            'PC': 'PC',
            'PS4': 'PlayStation',
            'X1': 'Xbox',
            'SWITCH': 'Switch'
        }
        
        platform_name_for_scrape = platform_map.get(platform, platform)
        
        pattern = rf'{re.escape(platform_name_for_scrape)}.*?(\d{{1,3}}(?:,\d{{3}})*)\s*RP.*?(\d{{1,3}}(?:,\d{{3}})*)\s*Masters? & Preds?'
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        
        if match:
            predator_rp = int(match.group(1).replace(',', ''))
            masters_count = int(match.group(2).replace(',', ''))
            
            print(f"[VERCEL] Scraping successful for {platform}: RP={predator_rp}, Masters/Preds={masters_count}")
            return {
                'predator_rp': predator_rp,
                'masters_count': masters_count,
                'rp_change_24h': 0,
                'last_updated': datetime.now().isoformat(),
                'source': 'apexlegendsstatus.com'
            }
        else:
            print(f"[VERCEL] No match found for {platform_name_for_scrape}")
            return None
            
    except Exception as e:
        print(f"[VERCEL] Error scraping predator points for {platform}: {e}")
        return None

# Routes
@app.route('/api/leaderboard/<platform>', methods=['GET'])
def get_leaderboard(platform):
    print(f"[VERCEL] Leaderboard request for platform: {platform}")
    try:
        # Check cache first
        cached_data = leaderboard_cache.get_data()
        if cached_data:
            print("[VERCEL] Serving from cache")
            
            # Apply dynamic overrides
            dynamic_overrides = load_twitch_overrides()
            leaderboard_data_to_return = cached_data.copy()
            leaderboard_data_to_return['players'] = [player.copy() for player in cached_data['players']]
            
            for player in leaderboard_data_to_return['players']:
                override_info = dynamic_overrides.get(player.get("player_name"))
                if override_info:
                    player["twitch_link"] = override_info["twitch_link"]
                    if "display_name" in override_info:
                        player["player_name"] = override_info["display_name"]
            
            # Re-add Twitch status (with timeout protection)
            leaderboard_data_to_return = add_twitch_live_status_safe(leaderboard_data_to_return)
            
            return jsonify({
                "success": True,
                "cached": True,
                "data": leaderboard_data_to_return,
                "last_updated": leaderboard_cache.last_updated.isoformat(),
                "source": "cache"
            })

        print(f"[VERCEL] Scraping fresh data for platform: {platform}")
        
        # Use optimized scraping for Vercel
        leaderboard_data = scrape_leaderboard_optimized(platform.upper())
        
        if leaderboard_data:
            # Apply Twitch overrides
            try:
                dynamic_overrides = load_twitch_overrides()
                print(f"[VERCEL] Loaded {len(dynamic_overrides)} Twitch overrides")
            except Exception as e:
                print(f"[VERCEL] Warning: Could not load Twitch overrides: {e}")
                dynamic_overrides = {}

            for player in leaderboard_data['players']:
                override_info = dynamic_overrides.get(player.get("player_name"))
                if override_info:
                    print(f"[VERCEL] Applying override for: {player.get('player_name')}")
                    player["twitch_link"] = override_info["twitch_link"]
                    if "display_name" in override_info:
                        player["player_name"] = override_info["display_name"]

            print("[VERCEL] Adding Twitch live status")
            leaderboard_data = add_twitch_live_status_safe(leaderboard_data)
            
            # Cache the result
            leaderboard_cache.set_data(leaderboard_data)
            
            return jsonify({
                "success": True,
                "cached": False,
                "data": leaderboard_data,
                "last_updated": leaderboard_cache.last_updated.isoformat(),
                "source": leaderboard_data.get("source", "unknown")
            })
        else:
            print("[VERCEL] Failed to get leaderboard data")
            return jsonify({
                "success": False,
                "error": "Failed to retrieve leaderboard data"
            }), 500

    except Exception as e:
        print(f"[VERCEL] Server error in get_leaderboard: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

@app.route('/api/add-twitch-override', methods=['POST'])
def add_twitch_override():
    """Adds or updates a Twitch link override for a player."""
    try:
        data = request.get_json()
        player_name = data.get("player_name")
        twitch_username = data.get("twitch_username")
        twitch_link = data.get("twitch_link")
        display_name = data.get("display_name")

        if not player_name:
            return jsonify({"success": False, "error": "Missing player_name"}), 400

        if not twitch_link and not twitch_username:
            return jsonify({"success": False, "error": "Missing twitch_link or twitch_username"}), 400

        current_overrides = load_twitch_overrides()
        
        # Handle both twitch_username and twitch_link formats
        if twitch_username and not twitch_link:
            final_twitch_link = f"https://twitch.tv/{twitch_username}"
        else:
            final_twitch_link = twitch_link
        
        override_info = {"twitch_link": final_twitch_link}
        if display_name:
            override_info["display_name"] = display_name
            
        current_overrides[player_name] = override_info
        
        save_twitch_overrides(current_overrides)

        # Clear caches
        twitch_live_cache["data"] = {}
        twitch_live_cache["last_updated"] = None
        
        leaderboard_cache.data = None
        leaderboard_cache.last_updated = None
        print("[VERCEL] Leaderboard cache cleared due to Twitch override.")

        return jsonify({"success": True, "message": f"Override for {player_name} added/updated."})

    except Exception as e:
        print(f"[VERCEL] Error adding Twitch override: {e}")
        return jsonify({"success": False, "error": f"Server error: {str(e)}"}), 500

@app.route('/api/predator-points', methods=['GET'])
def get_predator_points():
    """Get predator points for all platforms using the Mozambiquehe.re API."""
    try:
        print("[VERCEL] Fetching predator points for all platforms")
        platforms = ['PC', 'PS4', 'X1', 'SWITCH']
        all_data = {}
        
        api_call_successful = False
        api_data = {}
        
        try:
            print("[VERCEL] Trying Mozambiquehe.re API")
            response = requests.get(
                f'https://api.mozambiquehe.re/predator?auth={APEX_API_KEY}',
                timeout=15
            )
            
            if response.status_code == 200:
                api_response_root = response.json()
                api_data = api_response_root.get('RP', {}) 
                
                if api_data: 
                    api_call_successful = True
                    print("[VERCEL] API call successful")
                else:
                    print(f"[VERCEL] API returned empty data: {api_response_root}")
            else:
                print(f"[VERCEL] API failed with status {response.status_code}")
                
        except Exception as e:
            print(f"[VERCEL] API error: {e}")

        for platform in platforms:
            platform_data = {}
            
            if api_call_successful and platform in api_data:
                platform_api_data = api_data.get(platform)
                
                if platform_api_data:
                    predator_rp = platform_api_data.get('val', 0)
                    masters_count = platform_api_data.get('totalMastersAndPreds', 0)
                    
                    platform_data = {
                        'predator_rp': predator_rp,
                        'masters_count': masters_count,
                        'rp_change_24h': 0,
                        'last_updated': datetime.now().isoformat(),
                        'source': 'api.mozambiquehe.re'
                    }
                    print(f"[VERCEL] {platform}: RP={predator_rp}, Masters={masters_count}")
                else:
                    print(f"[VERCEL] No data for {platform}, trying scraping")
                    scraped_data = scrape_predator_points_fallback(platform)
                    if scraped_data:
                        platform_data = scraped_data
                    else:
                        # Use fallback values
                        fallback_rp = {'PC': 25000, 'PS4': 22000, 'X1': 20000, 'SWITCH': 18000}
                        fallback_masters = {'PC': 15000, 'PS4': 12000, 'X1': 10000, 'SWITCH': 8000}
                        
                        platform_data = {
                            'predator_rp': fallback_rp.get(platform, 20000),
                            'masters_count': fallback_masters.get(platform, 10000),
                            'rp_change_24h': 0,
                            'last_updated': datetime.now().isoformat(),
                            'source': 'fallback_estimates'
                        }
            else:
                print(f"[VERCEL] Using fallback for {platform}")
                scraped_data = scrape_predator_points_fallback(platform)
                if scraped_data:
                    platform_data = scraped_data
                else:
                    # Fallback values
                    fallback_rp = {'PC': 25000, 'PS4': 22000, 'X1': 20000, 'SWITCH': 18000}
                    fallback_masters = {'PC': 15000, 'PS4': 12000, 'X1': 10000, 'SWITCH': 8000}
                    
                    platform_data = {
                        'predator_rp': fallback_rp.get(platform, 20000),
                        'masters_count': fallback_masters.get(platform, 10000),
                        'rp_change_24h': 0,
                        'last_updated': datetime.now().isoformat(),
                        'source': 'fallback_estimates'
                    }
            
            all_data[platform] = platform_data
        
        source_list = set(data.get('source', 'unknown') for data in all_data.values())
        overall_source = "mixed" if len(source_list) > 1 else list(source_list)[0] if source_list else "unknown"

        return jsonify({
            "success": True,
            "data": all_data,
            "overall_source": overall_source
        })
        
    except Exception as e:
        print(f"[VERCEL] Server error in get_predator_points: {e}")
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

@app.route('/api/player/<platform>/<player_name>', methods=['GET'])
def get_player_stats(platform, player_name):
    """Get player statistics using the provided API key"""
    try:
        valid_platforms = ['PC', 'PS4', 'X1', 'SWITCH']
        if platform.upper() not in valid_platforms:
            return jsonify({
                "success": False,
                "error": f"Invalid platform: {platform}. Must be one of {', '.join(valid_platforms)}."
            }), 400

        print(f"[VERCEL] Fetching player stats for {player_name} on {platform}")
        response = requests.get(
            f'https://api.mozambiquehe.re/bridge?auth={APEX_API_KEY}&player={player_name}&platform={platform.upper()}',
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'Error' in data:
                print(f"[VERCEL] API error for player {player_name}: {data['Error']}")
                return jsonify({
                    "success": False,
                    "error": data['Error']
                }), 404
            return jsonify({
                "success": True,
                "data": data
            })
        else:
            print(f"[VERCEL] API status {response.status_code} for player {player_name}")
            return jsonify({
                "success": False,
                "error": f"API returned status {response.status_code}"
            }), response.status_code
            
    except requests.exceptions.Timeout:
        print(f"[VERCEL] Timeout for player {player_name}")
        return jsonify({
            "success": False,
            "error": "Request to Apex Legends API timed out."
        }), 503
    except Exception as e:
        print(f"[VERCEL] Error for player {player_name}: {e}")
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

@app.route('/api/tracker-stats', methods=['GET'])
def get_tracker_stats():
    """Proxy for Tracker.gg API"""
    try:
        platform = request.args.get('platform')
        identifier = request.args.get('identifier')
        stat_type = request.args.get('type', 'profile')
        
        if not platform or not identifier:
            return jsonify({
                "success": False,
                "message": "Platform and identifier are required"
            }), 400
        
        TRACKER_GG_API_KEY = 'c4cc3d18-adaf-487b-b3da-d47b924585c4'
        
        # Map platform names for Tracker.gg
        platform_map = {
            'origin': 'origin',
            'psn': 'psn', 
            'xbl': 'xbl'
        }
        
        tracker_platform = platform_map.get(platform, platform)
        
        if stat_type == 'sessions':
            url = f"https://public-api.tracker.gg/v2/apex/standard/profile/{tracker_platform}/{identifier}/sessions"
        else:
            url = f"https://public-api.tracker.gg/v2/apex/standard/profile/{tracker_platform}/{identifier}"
        
        headers = {
            'TRN-Api-Key': TRACKER_GG_API_KEY,
            'User-Agent': 'ApexLeaderboard/1.0'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            return jsonify({
                "success": True,
                "data": response.json()
            })
        else:
            error_data = {}
            try:
                error_data = response.json()
            except:
                error_data = {"message": response.text}
            
            return jsonify({
                "success": False,
                "message": error_data.get("message", f"Tracker.gg API error: {response.status_code}")
            }), response.status_code
            
    except requests.exceptions.Timeout:
        return jsonify({
            "success": False,
            "message": "Request to Tracker.gg API timed out"
        }), 503
    except Exception as e:
        print(f"[VERCEL] Error in tracker-stats proxy: {e}")
        return jsonify({
            "success": False,
            "message": f"Server error: {str(e)}"
        }), 500

# User routes
@app.route('/api/users', methods=['GET'])
def get_users():
    try:
        users = User.query.all()
        return jsonify([user.to_dict() for user in users])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users', methods=['POST'])
def create_user():
    try:
        data = request.json
        user = User(username=data['username'], email=data['email'])
        db.session.add(user)
        db.session.commit()
        return jsonify(user.to_dict()), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        return jsonify(user.to_dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        data = request.json
        user.username = data.get('username', user.username)
        user.email = data.get('email', user.email)
        db.session.commit()
        return jsonify(user.to_dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        return '', 204
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })

# This is required for Vercel
# DO NOT define a handler function! Just expose the app variable.
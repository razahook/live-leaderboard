from flask import Blueprint, jsonify, request
import requests
import re
from datetime import datetime
import os
import json
import time # Added for time.sleep

# Correct import path for twitch_integration
from routes.twitch_integration import get_twitch_live_status, extract_twitch_username

# Import from cache_manager (no src)
from cache_manager import leaderboard_cache

apex_scraper_bp = Blueprint('apex_scraper', __name__)

APEX_API_KEY = os.environ.get("APEX_API_KEY")
if not APEX_API_KEY:
    print("Warning: APEX_API_KEY environment variable not found. API calls will fail.")
    APEX_API_KEY = None

# Define the path for the JSON file to store Twitch overrides
OVERRIDE_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'twitch_overrides.json')

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

# --- MODIFIED ROUTE: Clear leaderboard cache after override ---
@apex_scraper_bp.route('/add-twitch-override', methods=['POST'])
def add_twitch_override():
    """
    Adds or updates a Twitch link override for a player.
    Expects JSON body with: {"player_name": "...", "twitch_link": "...", "display_name": "..." (optional)}
    Also clears the leaderboard cache to ensure immediate update.
    """
    try:
        data = request.get_json()
        player_name = data.get("player_name")
        twitch_link = data.get("twitch_link")
        display_name = data.get("display_name")  # Optional

        if not player_name or not twitch_link:
            return jsonify({"success": False, "error": "Missing player_name or twitch_link"}), 400

        current_overrides = load_twitch_overrides()
        
        override_info = {"twitch_link": twitch_link}
        if display_name:
            override_info["display_name"] = display_name
            
        current_overrides[player_name] = override_info
        
        save_twitch_overrides(current_overrides)

        # Clear the main leaderboard cache to ensure immediate update
        leaderboard_cache["data"] = None
        leaderboard_cache["last_updated"] = None
        print("Leaderboard cache cleared due to Twitch override.")

        return jsonify({"success": True, "message": f"Override for {player_name} added/updated."})

    except Exception as e:
        print(f"Error adding Twitch override: {e}")
        return jsonify({"success": False, "error": f"Server error: {str(e)}"}), 500

@apex_scraper_bp.route('/limits', methods=['GET'])
def get_predator_points():
    """
    Get predator points for all platforms using a single API call.
    No caching - always fresh data.
    """
    try:
        # Single API call to get all platform data
        api_url = f'https://api.mozambiquehe.re/predator?auth={APEX_API_KEY}'
        print(f"Making API call to: {api_url}")
        response = requests.get(api_url, timeout=10)
        print(f"API response status: {response.status_code}")
        print(f"API response headers: {response.headers}")
        
        if response.status_code == 200:
            api_data = response.json()
            print("Successfully fetched predator points from API")
            print(f"API Response: {api_data}")  # Debug: Print the actual API response
            
            # Transform API data to expected format
            all_data = {}
            platforms = ['PC', 'PS4', 'X1', 'SWITCH']
            
            # Check if API returns data in a nested structure
            if isinstance(api_data, dict) and 'data' in api_data:
                api_data = api_data['data']
            elif isinstance(api_data, dict) and 'battle_royale' in api_data:
                api_data = api_data['battle_royale']
            elif isinstance(api_data, dict) and 'RP' in api_data:
                api_data = api_data['RP']
            
            # Map platform names to possible API variations
            platform_mapping = {
                'PC': ['PC', 'pc', 'computer'],
                'PS4': ['PS4', 'ps4', 'playstation', 'PlayStation', 'PS'],
                'X1': ['X1', 'x1', 'xbox', 'Xbox', 'XBOX'],
                'SWITCH': ['SWITCH', 'switch', 'Switch', 'nintendo']
            }
            
            for platform in platforms:
                # Try to find the platform data using different possible names
                platform_data = None
                platform_key = None
                
                for possible_name in platform_mapping.get(platform, [platform]):
                    if possible_name in api_data:
                        platform_data = api_data[possible_name]
                        platform_key = possible_name
                        break
                
                if platform_data:
                    print(f"Platform {platform} data (found as '{platform_key}'): {platform_data}")  # Debug: Print platform data
                    
                    # Map API fields to expected format based on actual API response
                    predator_rp = (
                        platform_data.get("val") or  # The actual predator RP value
                        platform_data.get("predator") or 
                        platform_data.get("predator_rp") or 
                        platform_data.get("rp") or 
                        platform_data.get("threshold") or 
                        300000
                    )
                    
                    rp_change_24h = (
                        platform_data.get("rp_change_24h") or 
                        platform_data.get("change_24h") or 
                        platform_data.get("change") or 
                        0
                    )
                    
                    masters_count = (
                        platform_data.get("totalMastersAndPreds") or  # The actual masters count
                        platform_data.get("masters_count") or 
                        platform_data.get("masters") or 
                        platform_data.get("count") or 
                        5000
                    )
                    
                    all_data[platform] = {
                        "predator_rp": predator_rp,
                        "rp_change_24h": rp_change_24h,
                        "masters_count": masters_count
                    }
                else:
                    print(f"Platform {platform} not found in API response")  # Debug: Platform missing
                    # Default values if platform not found
                    all_data[platform] = {
                        "predator_rp": 300000,
                        "rp_change_24h": 0,
                        "masters_count": 5000
                    }
            
            print(f"Final data structure being returned (success): {all_data}")
            return jsonify({
                "success": True,
                "data": all_data
            })
        else:
            print(f"API call failed with status code: {response.status_code}")
            print(f"API response text: {response.text}")
            # Return default data structure
            all_data = {}
            platforms = ['PC', 'PS4', 'X1', 'SWITCH']
            for platform in platforms:
                all_data[platform] = {
                    "predator_rp": 300000,
                    "rp_change_24h": 0,
                    "masters_count": 5000
                }
            
            print(f"Final data structure being returned (API failed): {all_data}")
            return jsonify({
                "success": True,
                "data": all_data
            })
                
    except Exception as e:
        print(f"Error in get_predator_points: {e}")
        # Return default data structure on error
        all_data = {}
        platforms = ['PC', 'PS4', 'X1', 'SWITCH']
        for platform in platforms:
            all_data[platform] = {
                "predator_rp": 300000,
                "rp_change_24h": 0,
                "masters_count": 5000
            }
        
        return jsonify({
            "success": True,
            "data": all_data
        })

def scrape_predator_points_fallback(platform):
    """
    Fallback function to scrape predator points from apexlegendsstatus.com
    """
    try:
        url = f"https://apexlegendsstatus.com/leaderboards/{platform.lower()}"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            print(f"Failed to fetch data for {platform}: {response.status_code}")
            return None
        
        # Extract predator points using multiple regex patterns
        content = response.text
        
        # Pattern 1: Look for predator points in table cells
        predator_patterns = [
            r'<td[^>]*>(\d{4,5})</td>\s*<td[^>]*>Predator</td>',
            r'Predator.*?(\d{4,5})',
            r'<td[^>]*>(\d{4,5})</td>\s*<td[^>]*>[^<]*Predator[^<]*</td>',
            r'(\d{4,5})\s*Predator',
            r'Predator\s*(\d{4,5})'
        ]
        
        predator_points = None
        for pattern in predator_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                # Convert to integer and find the highest value
                numbers = [int(match) for match in matches if match.isdigit()]
                if numbers:
                    predator_points = max(numbers)
                    print(f"Found predator points for {platform}: {predator_points}")
                    break
        
        if predator_points is None:
            # Fallback: extract any 4-5 digit number that might be predator points
            number_pattern = r'\b(\d{4,5})\b'
            matches = re.findall(number_pattern, content)
            if matches:
                numbers = [int(match) for match in matches if match.isdigit()]
                # Filter out obviously wrong numbers (too low or too high)
                valid_numbers = [n for n in numbers if 10000 <= n <= 99999]
                if valid_numbers:
                    predator_points = max(valid_numbers)
                    print(f"Found fallback predator points for {platform}: {predator_points}")
        
        if predator_points:
            return {
                "predator": predator_points,
                "source": "scraped"
            }
        else:
            print(f"No predator points found for {platform}")
            return None
            
    except Exception as e:
        print(f"Error scraping predator points for {platform}: {e}")
        return None

@apex_scraper_bp.route('/player/<platform>/<player_name>', methods=['GET'])
def get_player_stats(platform, player_name):
    """
    Get detailed stats for a specific player on a specific platform.
    """
    try:
        # Use the Mozambiquehe.re API for player stats
        url = f"https://api.mozambiquehe.re/bridge?auth={APEX_API_KEY}&player={player_name}&platform={platform}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return jsonify(data)
        else:
            return jsonify({"error": f"Failed to fetch player data: {response.status_code}"}), response.status_code
            
    except Exception as e:
        print(f"Error getting player stats: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@apex_scraper_bp.route('/map-rotation', methods=['GET'])
def get_map_rotation():
    """
    Get current map rotation information.
    """
    try:
        url = f"https://api.mozambiquehe.re/maprotation?auth={APEX_API_KEY}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return jsonify(data)
        else:
            return jsonify({"error": f"Failed to fetch map rotation: {response.status_code}"}), response.status_code
            
    except Exception as e:
        print(f"Error getting map rotation: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500





@apex_scraper_bp.route('/news', methods=['GET'])
def get_news():
    """
    Get latest Apex Legends news
    """
    try:
        lang = request.args.get('lang', 'en-US')
        print(f"Making news API call to: https://api.mozambiquehe.re/news?auth={APEX_API_KEY[:8]}...&lang={lang}")
        response = requests.get(
            f'https://api.mozambiquehe.re/news?auth={APEX_API_KEY}&lang={lang}',
            timeout=10
        )
        print(f"News API response status: {response.status_code}")
        print(f"News API response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"News API response data: {data}")
            return jsonify({"success": True, "data": data})
        else:
            print(f"News API error response: {response.text}")
            return jsonify({"success": False, "error": f"API call failed with status code: {response.status_code}"}), 500
    except Exception as e:
        print(f"Exception in news: {e}")
        return jsonify({"success": False, "error": f"Server error: {str(e)}"}), 500


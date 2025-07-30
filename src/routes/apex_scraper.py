from flask import Blueprint, jsonify, request
import requests
import re
from datetime import datetime
import os
import json

# Correct import path for twitch_integration
from src.routes.twitch_integration import get_twitch_live_status, extract_twitch_username, twitch_live_cache

# FIXED: Import from separate cache module instead of circular import
from src.cache_manager import leaderboard_cache

apex_scraper_bp = Blueprint('apex_scraper', __name__)

APEX_API_KEY = "456c01cf240c13399563026f5604d777"

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
@apex_scraper_bp.route('/api/add-twitch-override', methods=['POST'])
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

        # Clear Twitch live status cache to ensure new data is fetched for this player
        twitch_live_cache["data"] = {}
        twitch_live_cache["last_updated"] = None
        
        # --- FIXED: Clear the main leaderboard cache as well ---
        leaderboard_cache.clear()
        print("Leaderboard cache cleared due to Twitch override.")
        # --- END FIX ---

        return jsonify({"success": True, "message": f"Override for {player_name} added/updated."})

    except Exception as e:
        print(f"Error adding Twitch override: {e}")
        return jsonify({"success": False, "error": f"Server error: {str(e)}"}), 500

@apex_scraper_bp.route('/api/predator-points', methods=['GET'])
def get_predator_points():
    """
    Get predator points for all platforms using the correct Mozambiquehe.re API.
    Includes a fallback to scraping if the API fails for a specific platform.
    """
    try:
        platforms = ['PC', 'PS4', 'X1', 'SWITCH']  # These platform keys are typically used by the API
        all_data = {}
        
        api_call_successful = False
        api_data = {}  # Initialize api_data outside the try/except
        try:
            response = requests.get(
                f'https://api.mozambiquehe.re/predator?auth={APEX_API_KEY}',
                timeout=10
            )
            
            if response.status_code == 200:
                api_response_root = response.json()
                api_data = api_response_root.get('RP', {}) 
                
                if api_data: 
                    api_call_successful = True
                    print("Successfully fetched predator data from api.mozambiquehe.re")
                else:
                    print(f"API returned 200 but 'RP' data is missing or empty. Response: {api_response_root}")
            else:
                print(f"API failed to fetch predator data with status {response.status_code}.")
                print(f"API Error Details: {response.text}")
                
        except requests.exceptions.Timeout:
            print("Timeout fetching API data for predator points. Will attempt scraping.")
        except requests.exceptions.RequestException as req_err:
            print(f"Request error fetching API data for predator points: {req_err}. Will attempt scraping.")
        except Exception as e:
            print(f"General error fetching API data for predator points: {e}. Will attempt scraping.")

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
                    print(f"Data for {platform} extracted from API: RP={predator_rp}, Masters={masters_count}.")
                else:
                    print(f"No specific predator data found for {platform} in API response's 'RP' object. Falling back to scraping.")
                    scraped_data = scrape_predator_points_fallback(platform)
                    if scraped_data:
                        platform_data = scraped_data
                    else:
                        print(f"Scraping also failed for {platform}.")
                        platform_data = {
                            'error': 'API data missing and scraping failed to retrieve data',
                            'last_updated': datetime.now().isoformat()
                        }
            else:
                print(f"API call failed initially. Falling back to scraping for {platform}.")
                scraped_data = scrape_predator_points_fallback(platform)
                if scraped_data:
                    platform_data = scraped_data
                else:
                    print(f"Scraping also failed for {platform}.")
                    platform_data = {
                        'error': 'API failed and scraping failed to retrieve data',
                        'last_updated': datetime.now().isoformat()
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
        print(f"Server error in get_predator_points: {e}")
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

def scrape_predator_points_fallback(platform):
    """
    Fallback scraping method for predator points from apexlegendsstatus.com.
    """
    try:
        url = "https://apexlegendsstatus.com/points-for-predator"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        print(f"Attempting to scrape predator points for {platform} from {url}")
        response = requests.get(url, headers=headers, timeout=10)
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
            
            print(f"Scraping successful for {platform}: RP={predator_rp}, Masters/Preds={masters_count}")
            return {
                'predator_rp': predator_rp,
                'masters_count': masters_count,
                'rp_change_24h': 0,
                'last_updated': datetime.now().isoformat(),
                'source': 'apexlegendsstatus.com'
            }
        else:
            print(f"No match found for regex pattern for {platform_name_for_scrape}. Content snippet: {content[:500]}...")
            return None
            
    except requests.exceptions.Timeout:
        print(f"Scraping timeout error for {platform}.")
        return None
    except requests.exceptions.RequestException as req_err:
        print(f"Scraping request error for {platform}: {req_err}")
        return None
    except Exception as e:
        print(f"General error scraping predator points for {platform}: {e}")
        return None

@apex_scraper_bp.route('/player/<platform>/<player_name>', methods=['GET'])
def get_player_stats(platform, player_name):
    """
    Get player statistics using the provided API key
    """
    try:
        valid_platforms = ['PC', 'PS4', 'X1', 'SWITCH']
        if platform.upper() not in valid_platforms:
            return jsonify({
                "success": False,
                "error": f"Invalid platform: {platform}. Must be one of {', '.join(valid_platforms)}."
            }), 400

        print(f"Fetching player stats for {player_name} on {platform}")
        response = requests.get(
            f'https://api.mozambiquehe.re/bridge?auth={APEX_API_KEY}&player={player_name}&platform={platform.upper()}',
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'Error' in data:
                print(f"API returned an error for player {player_name}: {data['Error']}")
                return jsonify({
                    "success": False,
                    "error": data['Error']
                }), 404
            return jsonify({
                "success": True,
                "data": data
            })
        else:
            print(f"API returned status {response.status_code} for player {player_name}: {response.text}")
            return jsonify({
                "success": False,
                "error": f"API returned status {response.status_code}: {response.text}"
            }), response.status_code
            
    except requests.exceptions.Timeout:
        print(f"Timeout fetching player stats for {player_name} on {platform}")
        return jsonify({
            "success": False,
            "error": "Request to Apex Legends API timed out."
        }), 503
    except requests.exceptions.RequestException as e:
        print(f"Request error fetching player stats for {player_name} on {platform}: {e}")
        return jsonify({
            "success": False,
            "error": f"Network or API request error: {str(e)}"
        }), 500
    except Exception as e:
        print(f"Server error in get_player_stats for {player_name}: {e}")
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

@apex_scraper_bp.route('/map-rotation', methods=['GET'])
def get_map_rotation():
    """
    Get current map rotation using the provided API key.
    """
    try:
        print("Fetching map rotation data.")
        response = requests.get(
            f'https://api.mozambiquehe.re/maprotation?auth={APEX_API_KEY}&version=2',
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                "success": True,
                "data": data
            })
        else:
            print(f"API returned status {response.status_code} for map rotation: {response.text}")
            return jsonify({
                "success": False,
                "error": f"API returned status {response.status_code}: {response.text}"
            }), response.status_code
            
    except requests.exceptions.Timeout:
        print("Timeout fetching map rotation.")
        return jsonify({
            "success": False,
            "error": "Request to Apex Legends API timed out for map rotation."
        }), 503
    except requests.exceptions.RequestException as e:
        print(f"Request error fetching map rotation: {e}")
        return jsonify({
            "success": False,
            "error": f"Network or API request error for map rotation: {str(e)}"
        }), 500
    except Exception as e:
        print(f"Server error in get_map_rotation: {e}")
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500
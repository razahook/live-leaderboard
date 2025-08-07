from flask import Blueprint, jsonify
import requests
from bs4 import BeautifulSoup

twitch_debug_override_bp = Blueprint('twitch_debug_override', __name__)

@twitch_debug_override_bp.route('/debug/override-test', methods=['GET'])
def debug_override_test():
    """Debug endpoint to test override application logic"""
    try:
        # Get raw leaderboard data first (before Twitch processing)
        base_url = "https://apexlegendsstatus.com/live-ranked-leaderboards/Battle_Royale/PC"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(base_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract first 20 player names
        player_names = []
        for row in soup.find_all("tr")[:21]:  # Skip header row
            if row.find("td"):
                rank_cell = row.find("td")
                if rank_cell:
                    # Try to extract rank
                    rank_text = rank_cell.get_text(strip=True)
                    if rank_text.isdigit():
                        rank = int(rank_text)
                        if 1 <= rank <= 20:
                            player_info_cell = row.find_all("td")[1] if len(row.find_all("td")) > 1 else None
                            if player_info_cell:
                                # Extract player name
                                name_div = player_info_cell.find("div", class_="player")
                                if name_div:
                                    player_name = name_div.get_text(strip=True)
                                    player_names.append({
                                        "rank": rank,
                                        "name": player_name
                                    })
        
        # Test hardcoded overrides
        hardcoded_overrides = {
            "ROC Vaxlon": {"twitch_link": "https://www.twitch.tv/vaxlon"},
            "ROC sauceror": {"twitch_link": "https://www.twitch.tv/sauceror"}, 
            "4rufq": {"twitch_link": "https://www.twitch.tv/4rufq"},
            "RemixPowers": {"twitch_link": "https://www.twitch.tv/remixpowers"},
            "LG_Naughty": {"twitch_link": "https://www.twitch.tv/Naughty"},
            "ImperialHal": {"twitch_link": "https://www.twitch.tv/tsm_imperialhal"}
        }
        
        # Check for matches
        matches_found = []
        for player in player_names:
            name = player["name"]
            if name in hardcoded_overrides:
                matches_found.append({
                    "rank": player["rank"],
                    "name": name,
                    "twitch_link": hardcoded_overrides[name]["twitch_link"],
                    "matched": True
                })
            else:
                matches_found.append({
                    "rank": player["rank"], 
                    "name": name,
                    "matched": False
                })
        
        return jsonify({
            "success": True,
            "total_players_scraped": len(player_names),
            "hardcoded_overrides_count": len(hardcoded_overrides),
            "players_with_matches": [p for p in matches_found if p.get("matched")],
            "players_without_matches": [p for p in matches_found if not p.get("matched")],
            "all_player_names": [p["name"] for p in player_names],
            "override_keys": list(hardcoded_overrides.keys())
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        })
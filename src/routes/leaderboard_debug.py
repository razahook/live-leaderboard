from flask import Blueprint, jsonify
import requests
from bs4 import BeautifulSoup
import re

leaderboard_debug_bp = Blueprint('leaderboard_debug', __name__)

@leaderboard_debug_bp.route('/debug/raw-scrape', methods=['GET'])
def debug_raw_scrape():
    """Debug the raw leaderboard scraping to see what Twitch links are actually found"""
    try:
        base_url = "https://apexlegendsstatus.com/live-ranked-leaderboards/Battle_Royale/PC"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        response = requests.get(base_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        players_found = []
        twitch_links_found = 0
        
        # Extract first 20 rows
        rows = soup.find_all("tr")[:21]  # Include header
        
        for i, row in enumerate(rows):
            if i == 0:  # Skip header
                continue
                
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
                
            # Get rank
            rank_cell = cells[0]
            rank_text = rank_cell.get_text(strip=True)
            
            if not rank_text.isdigit():
                continue
                
            rank = int(rank_text)
            if rank > 20:
                break
                
            # Get player info cell - it's the 3rd cell (index 2), not the 2nd
            if len(cells) < 3:
                continue
            player_info_cell = cells[2]
            
            # Extract player name - using EXACT same logic as main leaderboard scraper
            player_name = ""
            
            # Method 1: Look for strong tag (same as main scraper)
            strong_tag = player_info_cell.find('strong')
            if strong_tag:
                player_name = strong_tag.get_text(strip=True)
            else:
                # Method 2: Fallback using regex splitting (same as main scraper)
                text_content = player_info_cell.get_text(separator=' ', strip=True)
                name_part = re.split(r'(In\s+(?:lobby|match)|Offline|Playing|History|Performance|Lvl\s*\d+|\d+\s*RP\s+away|twitch\.tv)', text_content, 1)[0].strip()
                player_name = re.sub(r'^\W+|\W+$', '', name_part)  # Remove leading/trailing non-alphanumeric
            
            # If still no name, use a generic one
            if not player_name:
                player_name = f"Player{rank}"
            
            # Extract Twitch links - using EXACT same logic as main leaderboard scraper
            twitch_link = ""
            twitch_found_method = None
            
            # Method 1: Check for specific apexlegendsstatus.com redirect link
            twitch_anchor = player_info_cell.find("a", href=re.compile(r"apexlegendsstatus\.com/core/out\?type=twitch&id="))
            if not twitch_anchor:
                # Also check for Twitch icon link directly
                twitch_anchor = player_info_cell.find("a", class_=lambda x: x and "fa-twitch" in x, href=re.compile(r"apexlegendsstatus\.com/core/out\?type=twitch&id="))

            if twitch_anchor:
                from routes.twitch_integration import extract_twitch_username
                extracted_username = extract_twitch_username(twitch_anchor["href"])
                if extracted_username:
                    twitch_link = f"https://twitch.tv/{extracted_username}"
                    twitch_found_method = "redirect_link"
            else:
                # Fallback: search for twitch.tv URL within the cell's text or HTML
                twitch_match = re.search(r'(?:https?://)?(?:www\.)?twitch\.tv/([a-zA-Z0-9_]+)', player_info_cell.get_text(separator=' ', strip=True))
                if twitch_match:
                    username = twitch_match.group(1)
                    username = re.sub(r'(In|Offline|match|lobby)$', '', username, flags=re.IGNORECASE)
                    if username:
                        twitch_link = f"https://twitch.tv/{username}"
                        twitch_found_method = "text_search"
            
            # Method 4: Check for any mention of streaming/live status
            is_live_mentioned = False
            status_text = player_info_cell.get_text(separator=' ', strip=True).lower()
            if any(keyword in status_text for keyword in ["live", "streaming", "match", "lobby"]):
                is_live_mentioned = True
            
            if twitch_link:
                twitch_links_found += 1
            
            players_found.append({
                "rank": rank,
                "name": player_name,
                "twitch_link": twitch_link,
                "twitch_found_method": twitch_found_method,
                "has_twitch": bool(twitch_link),
                "is_live_mentioned": is_live_mentioned,
                "cell_text_preview": player_info_cell.get_text(separator=' ', strip=True)[:100]
            })
        
        # Add HTML structure debugging
        first_few_rows_html = []
        for i, row in enumerate(rows[:6]):  # First 5 rows + header
            first_few_rows_html.append({
                "row_index": i,
                "html": str(row)[:500],  # First 500 chars
                "cells_count": len(row.find_all("td")),
                "text_content": row.get_text(separator=' | ', strip=True)[:200]
            })
        
        return jsonify({
            "success": True,
            "total_players": len(players_found),
            "twitch_links_found": twitch_links_found,
            "players_with_twitch": [p for p in players_found if p["has_twitch"]],
            "players_without_twitch": [p for p in players_found if not p["has_twitch"]],
            "all_players": players_found,
            "response_status": response.status_code,
            "content_length": len(response.content),
            "html_debug": {
                "total_rows_found": len(rows),
                "first_few_rows": first_few_rows_html,
                "page_title": soup.title.get_text() if soup.title else "No title found"
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        })
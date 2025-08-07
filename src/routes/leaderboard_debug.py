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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://apexlegendsstatus.com/",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Upgrade-Insecure-Requests": "1"
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
                
            # Get player info cell
            player_info_cell = cells[1]
            
            # Extract player name - try multiple methods
            player_name = "Unknown"
            
            # Method 1: div with class="player"
            name_div = player_info_cell.find("div", class_="player")
            if name_div:
                player_name = name_div.get_text(strip=True)
            
            # Method 2: Look for any div in the cell
            if player_name == "Unknown":
                all_divs = player_info_cell.find_all("div")
                for div in all_divs:
                    text = div.get_text(strip=True)
                    if text and not text.startswith("#") and len(text) > 2:
                        player_name = text
                        break
            
            # Method 3: Look for text nodes directly
            if player_name == "Unknown":
                cell_text = player_info_cell.get_text(separator='|', strip=True)
                text_parts = [part.strip() for part in cell_text.split('|') if part.strip()]
                for part in text_parts:
                    if not part.startswith("#") and len(part) > 2 and not part.isdigit():
                        player_name = part
                        break
            
            # Method 4: Look for strong/b tags
            if player_name == "Unknown":
                strong_tags = player_info_cell.find_all(['strong', 'b'])
                for tag in strong_tags:
                    text = tag.get_text(strip=True)
                    if text and len(text) > 2:
                        player_name = text
                        break
            
            # Look for Twitch links - check multiple patterns
            twitch_link = ""
            twitch_found_method = None
            
            # Method 1: apexlegendsstatus.com redirect links
            twitch_anchor = player_info_cell.find("a", href=re.compile(r"apexlegendsstatus\.com/core/out\?type=twitch&id="))
            if twitch_anchor:
                twitch_found_method = "redirect_link"
                href = twitch_anchor.get("href", "")
                # Try to extract from redirect
                if "id=" in href:
                    username = href.split("id=")[-1]
                    if username:
                        twitch_link = f"https://twitch.tv/{username}"
            
            # Method 2: Direct twitch.tv links
            if not twitch_link:
                all_links = player_info_cell.find_all("a")
                for link in all_links:
                    href = link.get("href", "")
                    if "twitch.tv" in href:
                        twitch_link = href
                        twitch_found_method = "direct_link"
                        break
            
            # Method 3: Text content search
            if not twitch_link:
                cell_text = player_info_cell.get_text(separator=' ', strip=True)
                twitch_match = re.search(r'(?:https?://)?(?:www\.)?twitch\.tv/([a-zA-Z0-9_]+)', cell_text)
                if twitch_match:
                    username = twitch_match.group(1)
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
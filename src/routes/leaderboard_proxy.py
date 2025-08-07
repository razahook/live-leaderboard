from flask import Blueprint, jsonify
import requests
import time

leaderboard_proxy_bp = Blueprint('leaderboard_proxy', __name__)

@leaderboard_proxy_bp.route('/debug/test-proxy', methods=['GET'])
def test_proxy():
    """Test using different methods to get leaderboard data"""
    results = {}
    
    # Method 1: Different user agent
    try:
        headers1 = {
            "User-Agent": "curl/7.68.0"
        }
        response1 = requests.get("https://apexlegendsstatus.com/live-ranked-leaderboards/Battle_Royale/PC", 
                                headers=headers1, timeout=10)
        results["curl_agent"] = {
            "status": response1.status_code,
            "content_length": len(response1.content),
            "has_table": "<table" in response1.text.lower(),
            "has_apex": "apex" in response1.text.lower(),
            "title_found": "<title>" in response1.text.lower()
        }
    except Exception as e:
        results["curl_agent"] = {"error": str(e)}
    
    # Method 2: Try mobile user agent
    try:
        headers2 = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"
        }
        response2 = requests.get("https://apexlegendsstatus.com/live-ranked-leaderboards/Battle_Royale/PC",
                                headers=headers2, timeout=10)
        results["mobile_agent"] = {
            "status": response2.status_code,
            "content_length": len(response2.content),
            "has_table": "<table" in response2.text.lower(),
            "has_apex": "apex" in response2.text.lower(),
            "title_found": "<title>" in response2.text.lower()
        }
    except Exception as e:
        results["mobile_agent"] = {"error": str(e)}
    
    # Method 3: Try API endpoint if it exists
    try:
        api_url = "https://apexlegendsstatus.com/api/leaderboard/PC"
        response3 = requests.get(api_url, timeout=10)
        results["api_attempt"] = {
            "status": response3.status_code,
            "content_length": len(response3.content),
            "is_json": response3.headers.get("content-type", "").startswith("application/json"),
            "content_preview": response3.text[:200] if response3.status_code == 200 else response3.text[:100]
        }
    except Exception as e:
        results["api_attempt"] = {"error": str(e)}
    
    # Method 4: Try without headers
    try:
        response4 = requests.get("https://apexlegendsstatus.com/live-ranked-leaderboards/Battle_Royale/PC", timeout=10)
        results["no_headers"] = {
            "status": response4.status_code,
            "content_length": len(response4.content),
            "has_table": "<table" in response4.text.lower(),
            "content_preview": response4.text[:300]
        }
    except Exception as e:
        results["no_headers"] = {"error": str(e)}
        
    # Method 5: Alternative data source check
    try:
        # Check if there's an alternative API or data source
        alt_response = requests.get("https://apexlegendsstatus.com/", timeout=10)
        results["homepage_check"] = {
            "status": alt_response.status_code,
            "has_leaderboard_links": "leaderboard" in alt_response.text.lower(),
            "has_api_references": "api" in alt_response.text.lower()
        }
    except Exception as e:
        results["homepage_check"] = {"error": str(e)}
    
    return jsonify({
        "success": True,
        "test_results": results,
        "summary": {
            "methods_tested": len(results),
            "working_methods": len([r for r in results.values() if isinstance(r, dict) and r.get("status") == 200])
        }
    })
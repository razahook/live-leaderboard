#!/usr/bin/env python3
"""
Test to reproduce the actual Twitch integration bug by simulating the 
real-world execution flow including both leaderboard cache and Twitch cache.
"""

import sys
import os
import json
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_real_world_bug():
    """Test that demonstrates the real-world Twitch integration bug"""
    print("🧪 Testing Real-World Twitch Integration Bug")
    print("=" * 50)
    
    # Import the functions we need to test
    from src.routes.leaderboard_scraper import get_leaderboard
    from src.routes.twitch_integration import twitch_live_cache
    from src.cache_manager import leaderboard_cache
    import src.routes.twitch_integration as twitch_module
    
    # Clear all caches
    leaderboard_cache.clear()
    twitch_live_cache["data"] = {}
    twitch_live_cache["last_updated"] = None
    
    # Create test overrides - simulate the problematic case
    test_overrides = {
        "LG_Naughty": {
            "twitch_link": "https://www.twitch.tv/Naughty"
        }
    }
    
    # Save test overrides
    override_file_path = "/home/runner/work/live-leaderboard/live-leaderboard/twitch_overrides.json"
    with open(override_file_path, 'w') as f:
        json.dump(test_overrides, f, indent=4)
    
    # Mock the scraping function to return predictable data
    original_scrape_leaderboard = None
    
    def mock_scrape_leaderboard(platform):
        return {
            "platform": platform,
            "players": [
                {
                    "rank": 1,
                    "player_name": "LG_Naughty",
                    "rp": 25000,
                    "rp_change_24h": 500,
                    "twitch_link": "https://twitch.tv/LG_Naughty_WRONG",  # Wrong original link
                    "level": 500,
                    "status": "In lobby"
                },
                {
                    "rank": 2,
                    "player_name": "ZeekoTV_",
                    "rp": 24500,
                    "rp_change_24h": 300,
                    "twitch_link": "https://twitch.tv/ZeekoTV_",  # Correct link
                    "level": 450,
                    "status": "In match"
                }
            ],
            "total_players": 2,
            "last_updated": datetime.now().isoformat()
        }
    
    # Mock Twitch API responses
    call_count = 0
    
    def mock_get_twitch_live_status(channels):
        nonlocal call_count
        call_count += 1
        print(f"📡 Twitch API call #{call_count} with channels: {channels}")
        
        # Simulate the bug where wrong usernames get cached
        result = {}
        for channel in channels:
            channel_lower = channel.lower()
            
            if channel_lower == "lg_naughty_wrong":
                # This should NOT happen after override, but might due to caching bug
                result[channel_lower] = {
                    "is_live": True,
                    "stream_data": {
                        "title": "WRONG Stream Data for LG_Naughty",
                        "game_name": "Apex Legends",
                        "viewer_count": 999,  # Wrong viewer count
                        "user_name": "lg_naughty_wrong"
                    }
                }
                print(f"  ❌ Returning WRONG data for {channel_lower}")
            elif channel_lower == "naughty":
                # This is the correct data after override
                result[channel_lower] = {
                    "is_live": True,
                    "stream_data": {
                        "title": "Naughty's Correct Stream",
                        "game_name": "Apex Legends",
                        "viewer_count": 1500,  # Correct viewer count
                        "user_name": "Naughty"
                    }
                }
                print(f"  ✅ Returning correct data for {channel_lower}")
            elif channel_lower == "zeekotv_":
                result[channel_lower] = {
                    "is_live": True,
                    "stream_data": {
                        "title": "ZeekoTV Stream",
                        "game_name": "Apex Legends",
                        "viewer_count": 800,
                        "user_name": "ZeekoTV_"
                    }
                }
                print(f"  ✅ Returning data for {channel_lower}")
            else:
                result[channel_lower] = {"is_live": False, "stream_data": None}
                print(f"  ➖ No data for {channel_lower}")
        
        return result
    
    # Set up mocks
    import src.routes.leaderboard_scraper as leaderboard_module
    original_scrape_leaderboard = leaderboard_module.scrape_leaderboard
    leaderboard_module.scrape_leaderboard = mock_scrape_leaderboard
    
    twitch_module.get_twitch_live_status._test_mode = True
    twitch_module.get_twitch_live_status._test_mock_function = mock_get_twitch_live_status
    
    try:
        # Simulate first request - this should cache the wrong data
        print("\n🔄 Simulation 1: Fresh leaderboard request")
        print("This simulates the first request that caches potentially wrong data")
        
        # We need to mock the Flask app context for testing
        from flask import Flask
        app = Flask(__name__)
        
        with app.app_context():
            # This would normally be called via Flask route
            from src.routes.leaderboard_scraper import get_leaderboard
            
            # Mock the jsonify function since we're not in a real Flask request
            original_jsonify = None
            try:
                from flask import jsonify as flask_jsonify
                original_jsonify = flask_jsonify
                
                def mock_jsonify(data):
                    return data
                
                import src.routes.leaderboard_scraper as lb_module
                lb_module.jsonify = mock_jsonify
                
                result1 = get_leaderboard("PC")
                
                print("\n📊 Result 1:")
                if isinstance(result1, dict) and 'data' in result1:
                    for player in result1['data']['players']:
                        stream = player.get('stream')
                        print(f"  {player['player_name']}: "
                              f"link='{player.get('twitch_link', 'None')}', "
                              f"live={player.get('twitch_live', {}).get('is_live')}, "
                              f"viewers={stream.get('viewers') if stream else 'N/A'}, "
                              f"user={stream.get('twitchUser') if stream else 'N/A'}")
                
                # Simulate a small delay and another request
                print("\n🔄 Simulation 2: Cached leaderboard request")
                print("This simulates a subsequent request that should use cached data but re-apply overrides")
                
                # Advance time a bit but keep within cache period
                leaderboard_cache.last_updated = datetime.now() - timedelta(seconds=30)
                
                result2 = get_leaderboard("PC")
                
                print("\n📊 Result 2:")
                if isinstance(result2, dict) and 'data' in result2:
                    for player in result2['data']['players']:
                        stream = player.get('stream')
                        print(f"  {player['player_name']}: "
                              f"link='{player.get('twitch_link', 'None')}', "
                              f"live={player.get('twitch_live', {}).get('is_live')}, "
                              f"viewers={stream.get('viewers') if stream else 'N/A'}, "
                              f"user={stream.get('twitchUser') if stream else 'N/A'}")
                
                # Analyze the results
                print("\n🔍 Bug Analysis:")
                print("=" * 20)
                
                def analyze_result(result, label):
                    if isinstance(result, dict) and 'data' in result:
                        lg_naughty = next((p for p in result['data']['players'] if p['player_name'] == 'LG_Naughty'), None)
                        if lg_naughty:
                            stream = lg_naughty.get('stream')
                            link = lg_naughty.get('twitch_link', '')
                            user = stream.get('twitchUser') if stream else None
                            viewers = stream.get('viewers') if stream else None
                            
                            print(f"{label} - LG_Naughty:")
                            print(f"  Link: {link}")
                            print(f"  Stream User: {user}")
                            print(f"  Viewers: {viewers}")
                            
                            # Check for bugs
                            bugs = []
                            if 'WRONG' in link:
                                bugs.append("Still using wrong Twitch link")
                            if user and 'wrong' in user.lower():
                                bugs.append(f"Stream user shows wrong username: {user}")
                            if viewers == 999:
                                bugs.append(f"Shows wrong viewer count: {viewers}")
                            
                            if bugs:
                                print(f"  ❌ BUGS DETECTED: {', '.join(bugs)}")
                                return False
                            else:
                                print(f"  ✅ Data looks correct")
                                return True
                    return None
                
                result1_ok = analyze_result(result1, "Result 1")
                result2_ok = analyze_result(result2, "Result 2")
                
                print(f"\nOverall API calls made: {call_count}")
                
                if result1_ok is False or result2_ok is False:
                    print("❌ BUG CONFIRMED: Twitch integration has data leakage issues")
                elif result1_ok and result2_ok:
                    print("✅ No bugs detected in this test scenario")
                else:
                    print("❓ Test results inconclusive")
                
            finally:
                # Restore jsonify
                if original_jsonify:
                    lb_module.jsonify = original_jsonify
        
    finally:
        # Clean up mocks
        if original_scrape_leaderboard:
            leaderboard_module.scrape_leaderboard = original_scrape_leaderboard
        
        if hasattr(twitch_module.get_twitch_live_status, '_test_mode'):
            delattr(twitch_module.get_twitch_live_status, '_test_mode')
        if hasattr(twitch_module.get_twitch_live_status, '_test_mock_function'):
            delattr(twitch_module.get_twitch_live_status, '_test_mock_function')

if __name__ == "__main__":
    test_real_world_bug()
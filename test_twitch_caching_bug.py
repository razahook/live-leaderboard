#!/usr/bin/env python3
"""
Comprehensive test to reproduce the actual Twitch integration bug.

This test simulates the caching behavior and edge cases that can cause
Twitch data to leak between users.
"""

import sys
import os
import json
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_twitch_caching_bug():
    """Test that demonstrates the Twitch caching bug"""
    print("🧪 Testing Twitch Caching Bug")
    print("=" * 50)
    
    # Import the functions we need to test
    from src.routes.leaderboard_scraper import add_twitch_live_status
    from src.routes.twitch_integration import extract_twitch_username, twitch_live_cache
    from src.routes.apex_scraper import load_twitch_overrides
    import src.routes.twitch_integration as twitch_module
    
    # Clear any existing cache
    twitch_live_cache["data"] = {}
    twitch_live_cache["last_updated"] = None
    
    # Create test scenario 1: Initial leaderboard with original links
    scenario1_data = {
        "platform": "PC",
        "players": [
            {
                "rank": 1,
                "player_name": "LG_Naughty",
                "rp": 25000,
                "rp_change_24h": 500,
                "twitch_link": "https://twitch.tv/LG_Naughty",  # Original, wrong link
                "level": 500,
                "status": "In lobby"
            },
            {
                "rank": 2,
                "player_name": "ZeekoTV_",
                "rp": 24500,
                "rp_change_24h": 300,
                "twitch_link": "https://twitch.tv/ZeekoTV_",
                "level": 450,
                "status": "In match"
            }
        ],
        "total_players": 2,
        "last_updated": datetime.now().isoformat()
    }
    
    # Mock data for first scenario
    def mock_scenario1(channels):
        print(f"📡 Scenario 1 API call with: {channels}")
        return {
            "lg_naughty": {  # Wrong username in cache
                "is_live": True,
                "stream_data": {
                    "title": "Wrong Stream for LG_Naughty",
                    "game_name": "Apex Legends",
                    "viewer_count": 999,
                    "user_name": "lg_naughty"
                }
            },
            "zeekotv_": {
                "is_live": True,
                "stream_data": {
                    "title": "ZeekoTV Stream",
                    "game_name": "Apex Legends", 
                    "viewer_count": 800,
                    "user_name": "ZeekoTV_"
                }
            }
        }
    
    # Enable test mode for scenario 1
    twitch_module.get_twitch_live_status._test_mode = True
    twitch_module.get_twitch_live_status._test_mock_function = mock_scenario1
    
    print("\n📋 Scenario 1: Processing initial data with original links")
    scenario1_result = add_twitch_live_status(scenario1_data.copy())
    
    print("Scenario 1 results:")
    for player in scenario1_result['players']:
        stream = player.get('stream')
        print(f"  {player['player_name']}: live={player.get('twitch_live', {}).get('is_live')}, "
              f"viewers={stream.get('viewers') if stream else 'N/A'}, "
              f"user={stream.get('twitchUser') if stream else 'N/A'}")
    
    # Now apply overrides (simulating what happens in the actual leaderboard endpoint)
    print("\n🔧 Applying Twitch overrides...")
    test_overrides = {
        "LG_Naughty": {
            "twitch_link": "https://www.twitch.tv/Naughty"  # Correct override
        }
    }
    
    # Save overrides
    override_file_path = "/home/runner/work/live-leaderboard/live-leaderboard/twitch_overrides.json"
    with open(override_file_path, 'w') as f:
        json.dump(test_overrides, f, indent=4)
    
    # Create scenario 2: Same data but with overrides applied
    scenario2_data = scenario1_data.copy()
    scenario2_data['players'] = [p.copy() for p in scenario1_data['players']]
    
    # Apply overrides
    overrides = load_twitch_overrides()
    for player in scenario2_data['players']:
        override_info = overrides.get(player.get("player_name"))
        if override_info:
            print(f"  Override applied to {player['player_name']}: {override_info['twitch_link']}")
            player["twitch_link"] = override_info["twitch_link"]
    
    # Mock data for second scenario - with correct usernames
    def mock_scenario2(channels):
        print(f"📡 Scenario 2 API call with: {channels}")
        return {
            "naughty": {  # Correct username now
                "is_live": True,
                "stream_data": {
                    "title": "Naughty's Correct Stream",
                    "game_name": "Apex Legends",
                    "viewer_count": 1500,
                    "user_name": "Naughty"
                }
            },
            "zeekotv_": {
                "is_live": True,
                "stream_data": {
                    "title": "ZeekoTV Stream",
                    "game_name": "Apex Legends", 
                    "viewer_count": 800,
                    "user_name": "ZeekoTV_"
                }
            }
        }
    
    # Update mock for scenario 2
    twitch_module.get_twitch_live_status._test_mock_function = mock_scenario2
    
    print("\n📋 Scenario 2: Processing with overrides applied")
    scenario2_result = add_twitch_live_status(scenario2_data.copy())
    
    print("Scenario 2 results:")
    for player in scenario2_result['players']:
        stream = player.get('stream')
        print(f"  {player['player_name']}: live={player.get('twitch_live', {}).get('is_live')}, "
              f"viewers={stream.get('viewers') if stream else 'N/A'}, "
              f"user={stream.get('twitchUser') if stream else 'N/A'}")
    
    # Now test the caching issue - simulate cached data from scenario 1 being used in scenario 2
    print("\n🔄 Testing caching behavior...")
    
    # Manually set up cache with data from scenario 1 
    cache_key_old = "lg_naughty,zeekotv_"  # Old usernames
    cache_key_new = "naughty,zeekotv_"     # New usernames after override
    
    # Simulate that we have cached data from the first API call
    twitch_live_cache["data"][cache_key_old] = mock_scenario1([])
    twitch_live_cache["last_updated"] = datetime.now()
    
    # Now when we call with new usernames, it should not find cached data
    # and should make a new API call
    print(f"Cache keys: old='{cache_key_old}', new='{cache_key_new}'")
    print("Cache contents:", list(twitch_live_cache["data"].keys()))
    
    # The bug occurs when the cache key doesn't match due to username changes
    # Let's check what usernames are extracted for each scenario
    print("\n🔍 Username extraction analysis:")
    
    for scenario, data in [("Original", scenario1_data), ("Override", scenario2_data)]:
        print(f"\n{scenario} scenario usernames:")
        usernames = []
        for player in data['players']:
            if player.get('twitch_link'):
                username = extract_twitch_username(player['twitch_link'])
                usernames.append(username)
                print(f"  {player['player_name']}: {player['twitch_link']} -> {username}")
        cache_key = ",".join(sorted(usernames)) if usernames else ""
        print(f"  Cache key would be: '{cache_key}'")
    
    # Analyze the bug
    print("\n🐛 Bug Analysis:")
    print("=" * 20)
    
    # Check LG_Naughty specifically
    lg_scenario1 = next((p for p in scenario1_result['players'] if p['player_name'] == 'LG_Naughty'), None)
    lg_scenario2 = next((p for p in scenario2_result['players'] if p['player_name'] == 'LG_Naughty'), None)
    
    if lg_scenario1 and lg_scenario2:
        lg1_stream = lg_scenario1.get('stream', {})
        lg2_stream = lg_scenario2.get('stream', {})
        
        lg1_user = lg1_stream.get('twitchUser') if lg1_stream else None
        lg2_user = lg2_stream.get('twitchUser') if lg2_stream else None
        
        lg1_viewers = lg1_stream.get('viewers') if lg1_stream else None
        lg2_viewers = lg2_stream.get('viewers') if lg2_stream else None
        
        print(f"LG_Naughty comparison:")
        print(f"  Scenario 1 (original): user='{lg1_user}', viewers={lg1_viewers}")
        print(f"  Scenario 2 (override):  user='{lg2_user}', viewers={lg2_viewers}")
        
        if lg1_user != lg2_user or lg1_viewers != lg2_viewers:
            print("✅ Data correctly changed between scenarios (this is expected)")
        else:
            print("❌ Data did not change between scenarios (potential caching bug)")
    
    # Clean up
    if hasattr(twitch_module.get_twitch_live_status, '_test_mode'):
        delattr(twitch_module.get_twitch_live_status, '_test_mode')
    if hasattr(twitch_module.get_twitch_live_status, '_test_mock_function'):
        delattr(twitch_module.get_twitch_live_status, '_test_mock_function')
    
    print("\n✅ Test completed")

if __name__ == "__main__":
    test_twitch_caching_bug()
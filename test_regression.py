#!/usr/bin/env python3
"""
Comprehensive regression test for the Twitch integration fix.

This test specifically validates:
1. LG_Naughty with Twitch override to "Naughty" 
2. ZeekoTV_ with correct link and live status
3. Ensures no data leakage between users
4. Tests edge cases and multiple scenarios
"""

import sys
import os
import json
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_lg_naughty_zeekotv_regression():
    """Regression test for LG_Naughty and ZeekoTV_ specific issue"""
    print("🧪 LG_Naughty & ZeekoTV_ Regression Test")
    print("=" * 60)
    
    # Import the functions we need to test
    from src.routes.leaderboard_scraper import add_twitch_live_status
    from src.routes.twitch_integration import extract_twitch_username
    from src.routes.apex_scraper import load_twitch_overrides
    import src.routes.twitch_integration as twitch_module
    
    # Set up the exact scenario from the problem statement
    test_overrides = {
        "LG_Naughty": {
            "twitch_link": "https://www.twitch.tv/Naughty"  # Override to correct username
        }
        # ZeekoTV_ doesn't have an override, should use original link
    }
    
    # Save test overrides
    override_file_path = "/home/runner/work/live-leaderboard/live-leaderboard/twitch_overrides.json"
    with open(override_file_path, 'w') as f:
        json.dump(test_overrides, f, indent=4)
    
    # Create test leaderboard data - simulating the problematic scenario
    leaderboard_data = {
        "platform": "PC",
        "players": [
            {
                "rank": 1,
                "player_name": "LG_Naughty", 
                "rp": 25000,
                "rp_change_24h": 500,
                "twitch_link": "https://twitch.tv/lg_naughty_wrong",  # Wrong original link
                "level": 500,
                "status": "In lobby"
            },
            {
                "rank": 2,
                "player_name": "ZeekoTV_",
                "rp": 24500,
                "rp_change_24h": 300,
                "twitch_link": "https://twitch.tv/ZeekoTV_",  # Correct original link
                "level": 450,
                "status": "In match"
            },
            {
                "rank": 3,
                "player_name": "TestPlayer",
                "rp": 24000,
                "rp_change_24h": 200,
                "twitch_link": "",  # No Twitch link
                "level": 400,
                "status": "Offline"
            }
        ],
        "total_players": 3,
        "last_updated": datetime.now().isoformat()
    }
    
    print("📋 Initial test scenario:")
    for player in leaderboard_data['players']:
        print(f"  {player['player_name']}: {player.get('twitch_link', 'No link')}")
    
    # Apply overrides like the real leaderboard endpoint does
    print("\n🔧 Applying Twitch overrides...")
    overrides = load_twitch_overrides()
    
    for player in leaderboard_data['players']:
        override_info = overrides.get(player.get("player_name"))
        if override_info:
            print(f"  Override applied to {player['player_name']}: {override_info['twitch_link']}")
            player["twitch_link"] = override_info["twitch_link"]
        else:
            print(f"  No override for {player['player_name']}")
    
    print("\n🔍 Post-override links:")
    for player in leaderboard_data['players']:
        link = player.get('twitch_link', 'No link')
        username = extract_twitch_username(link) if link else None
        print(f"  {player['player_name']}: {link} -> {username}")
    
    # Mock Twitch API with realistic responses
    def mock_twitch_api(channels):
        print(f"\n📡 Twitch API called with channels: {channels}")
        
        # Simulate realistic Twitch API response
        mock_responses = {
            "naughty": {
                "is_live": True,
                "stream_data": {
                    "title": "Naughty's Apex Legends Stream",
                    "game_name": "Apex Legends",
                    "viewer_count": 1520,  # Specific viewer count for LG_Naughty
                    "started_at": "2024-01-01T10:00:00Z",
                    "thumbnail_url": "https://example.com/naughty_thumb.jpg",
                    "user_name": "Naughty"  # Correct username from API
                }
            },
            "zeekotv_": {
                "is_live": True,
                "stream_data": {
                    "title": "ZeekoTV_ Ranked Grind",
                    "game_name": "Apex Legends",
                    "viewer_count": 890,  # Specific viewer count for ZeekoTV_
                    "started_at": "2024-01-01T11:30:00Z",
                    "thumbnail_url": "https://example.com/zeeko_thumb.jpg",
                    "user_name": "ZeekoTV_"  # Correct username from API
                }
            },
            "lg_naughty_wrong": {
                # This should NOT be called since override should prevent it
                "is_live": False,
                "stream_data": None
            }
        }
        
        result = {}
        for channel in channels:
            channel_lower = channel.lower()
            if channel_lower in mock_responses:
                result[channel_lower] = mock_responses[channel_lower]
                is_live = mock_responses[channel_lower]["is_live"]
                print(f"  {channel} -> Live: {is_live}")
                if is_live:
                    viewers = mock_responses[channel_lower]["stream_data"]["viewer_count"]
                    print(f"    Viewers: {viewers}")
            else:
                result[channel_lower] = {"is_live": False, "stream_data": None}
                print(f"  {channel} -> Not live")
        
        return result
    
    # Set up mock
    twitch_module.get_twitch_live_status._test_mode = True
    twitch_module.get_twitch_live_status._test_mock_function = mock_twitch_api
    
    try:
        # Process the leaderboard data
        print("\n🔄 Processing Twitch live status...")
        result_data = add_twitch_live_status(leaderboard_data.copy())
        
        print("\n📊 Final Results:")
        print("=" * 30)
        
        test_results = []
        
        for player in result_data['players']:
            name = player['player_name']
            link = player.get('twitch_link', 'None')
            twitch_live = player.get('twitch_live', {})
            stream = player.get('stream')
            is_live = twitch_live.get('is_live', False)
            
            print(f"\n👤 {name}:")
            print(f"   Twitch Link: {link}")
            print(f"   Is Live: {is_live}")
            
            if stream:
                viewers = stream.get('viewers', 0)
                game = stream.get('game', 'Unknown')
                twitch_user = stream.get('twitchUser', 'Unknown')
                print(f"   Viewers: {viewers:,}")
                print(f"   Game: {game}")
                print(f"   Stream User: {twitch_user}")
                
                test_results.append({
                    'player': name,
                    'link': link,
                    'is_live': is_live,
                    'viewers': viewers,
                    'twitch_user': twitch_user
                })
            else:
                print(f"   Stream: None")
                test_results.append({
                    'player': name,
                    'link': link,
                    'is_live': is_live,
                    'viewers': 0,
                    'twitch_user': None
                })
        
        # Validate the results
        print("\n🔍 Validation:")
        print("=" * 20)
        
        validation_passed = True
        
        # Test 1: LG_Naughty should use override link and get correct data
        lg_naughty = next((r for r in test_results if r['player'] == 'LG_Naughty'), None)
        if lg_naughty:
            if "naughty" not in lg_naughty['link'].lower():
                print("❌ LG_Naughty: Override link not applied correctly")
                validation_passed = False
            elif not lg_naughty['is_live']:
                print("❌ LG_Naughty: Should be live but isn't")
                validation_passed = False
            elif lg_naughty['viewers'] != 1520:
                print(f"❌ LG_Naughty: Wrong viewer count {lg_naughty['viewers']}, expected 1520")
                validation_passed = False
            elif lg_naughty['twitch_user'] != 'Naughty':
                print(f"❌ LG_Naughty: Wrong stream user '{lg_naughty['twitch_user']}', expected 'Naughty'")
                validation_passed = False
            else:
                print("✅ LG_Naughty: All data correct")
        else:
            print("❌ LG_Naughty: Player not found in results")
            validation_passed = False
        
        # Test 2: ZeekoTV_ should use original link and get correct data  
        zeekotv = next((r for r in test_results if r['player'] == 'ZeekoTV_'), None)
        if zeekotv:
            if "zeekotv_" not in zeekotv['link'].lower():
                print("❌ ZeekoTV_: Original link not preserved")
                validation_passed = False
            elif not zeekotv['is_live']:
                print("❌ ZeekoTV_: Should be live but isn't")
                validation_passed = False
            elif zeekotv['viewers'] != 890:
                print(f"❌ ZeekoTV_: Wrong viewer count {zeekotv['viewers']}, expected 890")
                validation_passed = False
            elif zeekotv['twitch_user'] != 'ZeekoTV_':
                print(f"❌ ZeekoTV_: Wrong stream user '{zeekotv['twitch_user']}', expected 'ZeekoTV_'")
                validation_passed = False
            else:
                print("✅ ZeekoTV_: All data correct")
        else:
            print("❌ ZeekoTV_: Player not found in results")
            validation_passed = False
        
        # Test 3: TestPlayer should have no live data
        test_player = next((r for r in test_results if r['player'] == 'TestPlayer'), None)
        if test_player:
            if test_player['is_live']:
                print("❌ TestPlayer: Should not be live")
                validation_passed = False
            elif test_player['viewers'] != 0:
                print(f"❌ TestPlayer: Should have 0 viewers, got {test_player['viewers']}")
                validation_passed = False
            else:
                print("✅ TestPlayer: Correctly shows as not live")
        else:
            print("❌ TestPlayer: Player not found in results")
            validation_passed = False
        
        # Test 4: Ensure no data leakage (each player has unique appropriate data)
        live_players = [r for r in test_results if r['is_live']]
        if len(live_players) == 2:  # LG_Naughty and ZeekoTV_
            if (lg_naughty['viewers'] != zeekotv['viewers'] and 
                lg_naughty['twitch_user'] != zeekotv['twitch_user']):
                print("✅ No data leakage: Each player has unique stream data")
            else:
                print("❌ Data leakage detected: Players have identical stream data")
                validation_passed = False
        else:
            print(f"❌ Expected 2 live players, got {len(live_players)}")
            validation_passed = False
        
        print(f"\n🏁 Overall Result:")
        if validation_passed:
            print("✅ ALL TESTS PASSED - Twitch integration is working correctly!")
            return True
        else:
            print("❌ SOME TESTS FAILED - Twitch integration has issues")
            return False
    
    finally:
        # Clean up
        if hasattr(twitch_module.get_twitch_live_status, '_test_mode'):
            delattr(twitch_module.get_twitch_live_status, '_test_mode')
        if hasattr(twitch_module.get_twitch_live_status, '_test_mock_function'):
            delattr(twitch_module.get_twitch_live_status, '_test_mock_function')

if __name__ == "__main__":
    success = test_lg_naughty_zeekotv_regression()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Test script to reproduce and verify the Twitch integration bug fix.

This test creates a scenario with multiple players including:
- LG_Naughty with a Twitch override to "Naughty"
- ZeekoTV_ with their original link
- Regular players

The bug occurs when Twitch usernames get mixed up between players,
causing wrong live status and viewer counts to be assigned.
"""

import sys
import os
import json
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def create_test_leaderboard_data():
    """Create test leaderboard data with multiple players"""
    return {
        "platform": "PC",
        "players": [
            {
                "rank": 1,
                "player_name": "LG_Naughty",
                "rp": 25000,
                "rp_change_24h": 500,
                "twitch_link": "https://twitch.tv/LG_Naughty_Original",  # Original link
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

def create_test_twitch_overrides():
    """Create test Twitch overrides"""
    return {
        "LG_Naughty": {
            "twitch_link": "https://www.twitch.tv/Naughty"
        }
    }

def mock_twitch_live_status():
    """Mock Twitch live status for testing"""
    return {
        "naughty": {
            "is_live": True,
            "stream_data": {
                "title": "Naughty's Stream",
                "game_name": "Apex Legends",
                "viewer_count": 1500,
                "started_at": "2024-01-01T12:00:00Z",
                "thumbnail_url": "https://example.com/naughty_thumb.jpg",
                "user_name": "Naughty"
            }
        },
        "zeekotv_": {
            "is_live": True,
            "stream_data": {
                "title": "ZeekoTV Stream",
                "game_name": "Apex Legends", 
                "viewer_count": 800,
                "started_at": "2024-01-01T13:00:00Z",
                "thumbnail_url": "https://example.com/zeeko_thumb.jpg",
                "user_name": "ZeekoTV_"
            }
        }
    }

def test_twitch_integration_bug():
    """Test that demonstrates the Twitch integration bug"""
    print("🧪 Testing Twitch Integration Bug")
    print("=" * 50)
    
    # Import the functions we need to test
    from src.routes.leaderboard_scraper import add_twitch_live_status
    from src.routes.twitch_integration import extract_twitch_username
    from src.routes.apex_scraper import load_twitch_overrides
    
    # Create test data
    leaderboard_data = create_test_leaderboard_data()
    test_overrides = create_test_twitch_overrides()
    
    # Save test overrides to file for testing
    override_file_path = "/home/runner/work/live-leaderboard/live-leaderboard/twitch_overrides.json"
    with open(override_file_path, 'w') as f:
        json.dump(test_overrides, f, indent=4)
    
    print("📋 Initial test data:")
    for player in leaderboard_data['players']:
        print(f"  {player['player_name']}: {player['twitch_link']}")
    
    print("\n🔧 Applying overrides...")
    # Apply overrides manually like the leaderboard endpoint does
    overrides = load_twitch_overrides()
    for player in leaderboard_data['players']:
        override_info = overrides.get(player.get("player_name"))
        if override_info:
            print(f"  Override applied to {player['player_name']}: {override_info['twitch_link']}")
            player["twitch_link"] = override_info["twitch_link"]
    
    print("\n🔍 Username extraction:")
    for player in leaderboard_data['players']:
        if player.get('twitch_link'):
            username = extract_twitch_username(player['twitch_link'])
            print(f"  {player['player_name']} -> {username}")
    
    # Mock the Twitch API response by using the test mode
    import src.routes.twitch_integration as twitch_module
    
    def mock_get_twitch_live_status(channels):
        print(f"\n📡 Mock Twitch API called with channels: {channels}")
        mock_data = mock_twitch_live_status()
        result = {}
        for channel in channels:
            channel_lower = channel.lower()
            if channel_lower in mock_data:
                result[channel_lower] = mock_data[channel_lower]
                print(f"  Found live data for {channel_lower}")
            else:
                result[channel_lower] = {"is_live": False, "stream_data": None}
                print(f"  No live data for {channel_lower}")
        return result
    
    # Enable test mode
    twitch_module.get_twitch_live_status._test_mode = True
    twitch_module.get_twitch_live_status._test_mock_function = mock_get_twitch_live_status
    
    try:
        # Process live status
        print("\n🔄 Processing live status...")
        result_data = add_twitch_live_status(leaderboard_data)
        
        print("\n📊 Final results:")
        print("=" * 30)
        for player in result_data['players']:
            twitch_live = player.get('twitch_live', {})
            stream = player.get('stream')
            
            print(f"\n👤 {player['player_name']}:")
            print(f"   Twitch Link: {player.get('twitch_link', 'None')}")
            print(f"   Is Live: {twitch_live.get('is_live', False)}")
            if stream:
                print(f"   Viewers: {stream.get('viewers', 0)}")
                print(f"   Twitch User: {stream.get('twitchUser', 'None')}")
            
        # Check for the bug: verify each player has the correct data
        print("\n🔍 Bug Detection:")
        print("=" * 20)
        
        lg_naughty = next((p for p in result_data['players'] if p['player_name'] == 'LG_Naughty'), None)
        zeekoTV = next((p for p in result_data['players'] if p['player_name'] == 'ZeekoTV_'), None)
        
        bugs_detected = []
        
        if lg_naughty:
            lg_expected_username = extract_twitch_username(lg_naughty['twitch_link'])
            lg_stream = lg_naughty.get('stream')
            lg_actual_stream_user = lg_stream.get('twitchUser') if lg_stream else None
            print(f"LG_Naughty expected username: {lg_expected_username}")
            print(f"LG_Naughty actual stream user: {lg_actual_stream_user}")
            if lg_actual_stream_user and lg_expected_username:
                if lg_actual_stream_user.lower() != lg_expected_username.lower():
                    bugs_detected.append(f"LG_Naughty has wrong stream user: expected '{lg_expected_username}', got '{lg_actual_stream_user}'")
                    print("❌ BUG DETECTED: LG_Naughty has wrong stream user!")
                else:
                    print("✅ LG_Naughty stream user is correct")
            elif lg_expected_username and not lg_actual_stream_user:
                bugs_detected.append(f"LG_Naughty should be live (expected '{lg_expected_username}') but has no stream data")
                print("❌ BUG DETECTED: LG_Naughty should be live but has no stream data!")
        
        if zeekoTV:
            zeeko_expected_username = extract_twitch_username(zeekoTV['twitch_link'])
            zeeko_stream = zeekoTV.get('stream')
            zeeko_actual_stream_user = zeeko_stream.get('twitchUser') if zeeko_stream else None
            print(f"ZeekoTV_ expected username: {zeeko_expected_username}")
            print(f"ZeekoTV_ actual stream user: {zeeko_actual_stream_user}")
            if zeeko_actual_stream_user and zeeko_expected_username:
                if zeeko_actual_stream_user.lower() != zeeko_expected_username.lower():
                    bugs_detected.append(f"ZeekoTV_ has wrong stream user: expected '{zeeko_expected_username}', got '{zeeko_actual_stream_user}'")
                    print("❌ BUG DETECTED: ZeekoTV_ has wrong stream user!")
                else:
                    print("✅ ZeekoTV_ stream user is correct")
            elif zeeko_expected_username and not zeeko_actual_stream_user:
                bugs_detected.append(f"ZeekoTV_ should be live (expected '{zeeko_expected_username}') but has no stream data")
                print("❌ BUG DETECTED: ZeekoTV_ should be live but has no stream data!")
        
        if bugs_detected:
            print(f"\n❌ {len(bugs_detected)} bug(s) detected:")
            for bug in bugs_detected:
                print(f"   - {bug}")
            return False
        else:
            print("\n✅ No bugs detected! Twitch integration is working correctly.")
            return True
        
    finally:
        # Disable test mode
        if hasattr(twitch_module.get_twitch_live_status, '_test_mode'):
            delattr(twitch_module.get_twitch_live_status, '_test_mode')
        if hasattr(twitch_module.get_twitch_live_status, '_test_mock_function'):
            delattr(twitch_module.get_twitch_live_status, '_test_mock_function')

if __name__ == "__main__":
    test_twitch_integration_bug()
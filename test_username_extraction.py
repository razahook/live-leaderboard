#!/usr/bin/env python3
"""
Test username extraction edge cases that might cause bugs.
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_username_extraction():
    """Test username extraction for edge cases"""
    print("🧪 Testing Username Extraction Edge Cases")
    print("=" * 50)
    
    from src.routes.twitch_integration import extract_twitch_username
    
    test_cases = [
        # (input_link, expected_output, description)
        ("https://twitch.tv/Naughty", "naughty", "Basic HTTPS link"),
        ("https://www.twitch.tv/Naughty", "naughty", "HTTPS with www"),
        ("http://twitch.tv/ZeekoTV_", "zeekotv_", "HTTP link"),
        ("twitch.tv/ZeekoTV_", "zeekotv_", "No protocol"),
        ("ZeekoTV_", "zeekotv_", "Just username"),
        ("https://twitch.tv/ZeekoTV_/", "zeekotv_", "Trailing slash"),
        ("https://twitch.tv/ZeekoTV_?param=value", "zeekotv_", "Query parameters"),
        ("https://apexlegendsstatus.com/core/out?type=twitch&id=Naughty", "naughty", "ApexLegendsStatus redirect"),
        ("", None, "Empty string"),
        (None, None, "None input"),
        ("https://example.com/nottwitch", None, "Non-Twitch link"),
        ("https://twitch.tv/", None, "Empty username"),
        ("https://twitch.tv/User-With-Dash", None, "Username with dash (should fail)"),
        ("https://twitch.tv/User123_", "user123_", "Username with numbers and underscore"),
    ]
    
    bugs_found = []
    
    for i, (input_link, expected, description) in enumerate(test_cases, 1):
        try:
            result = extract_twitch_username(input_link)
            status = "✅" if result == expected else "❌"
            
            print(f"{i:2d}. {description}")
            print(f"    Input:    '{input_link}'")
            print(f"    Expected: {expected}")
            print(f"    Got:      {result}")
            print(f"    Status:   {status}")
            
            if result != expected:
                bugs_found.append((input_link, expected, result, description))
            
            print()
            
        except Exception as e:
            print(f"{i:2d}. {description}")
            print(f"    Input:    '{input_link}'")
            print(f"    ERROR:    {e}")
            print(f"    Status:   ❌")
            bugs_found.append((input_link, expected, f"ERROR: {e}", description))
            print()
    
    print("🔍 Summary:")
    print("=" * 20)
    if bugs_found:
        print(f"❌ {len(bugs_found)} bug(s) found in username extraction:")
        for input_link, expected, actual, desc in bugs_found:
            print(f"  - {desc}: '{input_link}' -> expected '{expected}', got '{actual}'")
        return False
    else:
        print("✅ All username extraction tests passed!")
        return True

def test_case_sensitivity_bug():
    """Test for case sensitivity issues that might cause data leakage"""
    print("\n🧪 Testing Case Sensitivity Issues")
    print("=" * 50)
    
    from src.routes.twitch_integration import extract_twitch_username
    from src.routes.leaderboard_scraper import add_twitch_live_status
    import src.routes.twitch_integration as twitch_module
    
    # Test data with mixed case
    test_data = {
        "platform": "PC",
        "players": [
            {
                "rank": 1,
                "player_name": "Player1",
                "rp": 25000,
                "rp_change_24h": 500,
                "twitch_link": "https://twitch.tv/TestUser",  # Capital T
                "level": 500,
                "status": "In lobby"
            },
            {
                "rank": 2,
                "player_name": "Player2", 
                "rp": 24500,
                "rp_change_24h": 300,
                "twitch_link": "https://twitch.tv/testuser",  # lowercase t
                "level": 450,
                "status": "In match"
            }
        ],
        "total_players": 2,
        "last_updated": "2024-01-01T12:00:00Z"
    }
    
    # Mock that returns data for both case variations
    def mock_case_sensitive(channels):
        print(f"📡 API called with: {channels}")
        result = {}
        for channel in channels:
            result[channel.lower()] = {
                "is_live": True,
                "stream_data": {
                    "title": f"Stream for {channel}",
                    "game_name": "Apex Legends",
                    "viewer_count": 100 + len(channel),  # Different count based on length
                    "user_name": channel  # Keep original case
                }
            }
        return result
    
    # Enable test mode
    twitch_module.get_twitch_live_status._test_mode = True
    twitch_module.get_twitch_live_status._test_mock_function = mock_case_sensitive
    
    try:
        result = add_twitch_live_status(test_data.copy())
        
        print("Results:")
        for player in result['players']:
            stream = player.get('stream')
            twitch_live = player.get('twitch_live', {})
            print(f"  {player['player_name']}:")
            print(f"    Link: {player['twitch_link']}")
            print(f"    Extracted: {extract_twitch_username(player['twitch_link'])}")
            print(f"    Live: {twitch_live.get('is_live')}")
            if stream:
                print(f"    Viewers: {stream.get('viewers')}")
                print(f"    Stream User: {stream.get('twitchUser')}")
            print()
        
        # Check for issues
        usernames = [extract_twitch_username(p['twitch_link']) for p in test_data['players'] if p.get('twitch_link')]
        unique_usernames = set(usernames)
        
        print(f"Extracted usernames: {usernames}")
        print(f"Unique usernames: {unique_usernames}")
        
        if len(usernames) != len(unique_usernames):
            print("ℹ️  Case sensitivity collision detected (this is expected behavior)")
            print("  Multiple players resolve to the same Twitch username")
            
            # Check that all players with the same username get the same data
            for username in unique_usernames:
                players_with_username = [i for i, u in enumerate(usernames) if u == username]
                if len(players_with_username) > 1:
                    print(f"  Checking players with username '{username}':")
                    first_player_data = None
                    for i, player_idx in enumerate(players_with_username):
                        player = result['players'][player_idx]
                        stream = player.get('stream')
                        viewers = stream.get('viewers') if stream else None
                        user = stream.get('twitchUser') if stream else None
                        
                        print(f"    Player {player_idx+1}: viewers={viewers}, user={user}")
                        
                        if i == 0:
                            first_player_data = (viewers, user)
                        elif (viewers, user) != first_player_data:
                            print("    ❌ BUG: Players with same username have different stream data!")
                            return False
                    print(f"    ✅ All players with username '{username}' have consistent data")
            
            print("✅ Case sensitivity handled correctly")
            return True
        else:
            print("✅ No case sensitivity issues detected")
            return True
            
    finally:
        # Clean up
        if hasattr(twitch_module.get_twitch_live_status, '_test_mode'):
            delattr(twitch_module.get_twitch_live_status, '_test_mode')
        if hasattr(twitch_module.get_twitch_live_status, '_test_mock_function'):
            delattr(twitch_module.get_twitch_live_status, '_test_mock_function')

if __name__ == "__main__":
    result1 = test_username_extraction()
    result2 = test_case_sensitivity_bug()
    
    print("\n🏁 Final Results:")
    print("=" * 20)
    if result1 and result2:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
        sys.exit(1)
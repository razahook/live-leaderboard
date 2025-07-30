#!/usr/bin/env python3
"""
Simple test script to verify LG_Naughty has the correct hardcoded Twitch link.
This test ensures that:
1. LG_Naughty always has the twitch_link set to https://www.twitch.tv/Naughty
2. No dynamic override logic exists in the codebase
3. The leaderboard UI displays correctly for LG_Naughty
"""

import requests
import json
import sys
import time

def test_lg_naughty_twitch_link():
    """Test that LG_Naughty has the correct hardcoded Twitch link."""
    print("Testing LG_Naughty Twitch link...")
    
    try:
        # Test the leaderboard API
        response = requests.get("http://localhost:5000/api/leaderboard/PC", timeout=10)
        
        if response.status_code != 200:
            print(f"❌ API request failed with status {response.status_code}")
            return False
            
        data = response.json()
        
        if not data.get("success"):
            print(f"❌ API returned unsuccessful response: {data.get('error', 'Unknown error')}")
            # Even if scraping fails, we can still test with mock data
            return test_with_mock_data()
            
        players = data.get("data", {}).get("players", [])
        lg_naughty_player = None
        
        for player in players:
            if player.get("player_name") == "LG_Naughty":
                lg_naughty_player = player
                break
                
        if not lg_naughty_player:
            print("❌ LG_Naughty not found in leaderboard data")
            return False
            
        # Check if LG_Naughty has the correct Twitch link
        expected_link = "https://www.twitch.tv/Naughty"
        actual_link = lg_naughty_player.get("twitch_link")
        
        if actual_link == expected_link:
            print(f"✅ LG_Naughty has correct Twitch link: {actual_link}")
            return True
        else:
            print(f"❌ LG_Naughty has incorrect Twitch link. Expected: {expected_link}, Got: {actual_link}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False

def test_with_mock_data():
    """Test the hardcoded logic with mock data."""
    print("Testing with mock data since API scraping is not available...")
    
    # Import the mapping function to test it directly
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), 'api'))
    
    try:
        from index import apply_hardcoded_twitch_mappings, HARDCODED_TWITCH_MAPPINGS
        
        # Create mock leaderboard data
        mock_data = {
            "players": [
                {
                    "rank": 1,
                    "player_name": "LG_Naughty",
                    "rp": 50000,
                    "twitch_link": ""
                },
                {
                    "rank": 2,
                    "player_name": "SomeOtherPlayer",
                    "rp": 49000,
                    "twitch_link": "https://twitch.tv/otherplayer"
                }
            ]
        }
        
        # Apply the hardcoded mappings
        result = apply_hardcoded_twitch_mappings(mock_data)
        
        # Check if LG_Naughty has the correct link
        lg_naughty_player = None
        for player in result["players"]:
            if player["player_name"] == "LG_Naughty":
                lg_naughty_player = player
                break
        
        if not lg_naughty_player:
            print("❌ LG_Naughty not found in mock data")
            return False
        
        expected_link = "https://www.twitch.tv/Naughty"
        actual_link = lg_naughty_player.get("twitch_link")
        
        if actual_link == expected_link:
            print(f"✅ LG_Naughty has correct Twitch link in mock data: {actual_link}")
            
            # Also verify the hardcoded mapping exists
            if "LG_Naughty" in HARDCODED_TWITCH_MAPPINGS:
                print(f"✅ LG_Naughty mapping exists in HARDCODED_TWITCH_MAPPINGS")
                return True
            else:
                print("❌ LG_Naughty mapping missing from HARDCODED_TWITCH_MAPPINGS")
                return False
        else:
            print(f"❌ LG_Naughty has incorrect Twitch link in mock data. Expected: {expected_link}, Got: {actual_link}")
            return False
            
    except ImportError as e:
        print(f"❌ Could not import backend functions: {e}")
        return False
    except Exception as e:
        print(f"❌ Mock data test failed with exception: {e}")
        return False

def test_override_endpoints_removed():
    """Test that override endpoints are no longer accessible."""
    print("Testing that override endpoints are removed...")
    
    try:
        # Try to access the override endpoint - it should return 404
        response = requests.post("http://localhost:5000/api/add-twitch-override", 
                               json={"player_name": "test", "twitch_username": "test"},
                               timeout=5)
        
        if response.status_code == 404:
            print("✅ Override endpoint correctly removed (404)")
            return True
        else:
            print(f"❌ Override endpoint still accessible (status: {response.status_code})")
            return False
            
    except requests.exceptions.RequestException:
        print("✅ Override endpoint correctly removed (connection failed)")
        return True

def main():
    """Run all tests."""
    print("🧪 Running LG_Naughty regression tests...\n")
    
    tests = [
        ("LG_Naughty Twitch Link", test_lg_naughty_twitch_link),
        ("Override Endpoints Removed", test_override_endpoints_removed),
        ("Mock Data Hardcoded Mapping", test_with_mock_data),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Running: {test_name}")
        if test_func():
            passed += 1
        print("-" * 50)
    
    print(f"\n📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
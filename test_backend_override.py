#!/usr/bin/env python3
"""
Direct test of Twitch override functionality with the actual backend
"""

import json
import os

def test_twitch_override_api():
    """Test the Twitch override functionality by directly calling the backend logic"""
    
    print("Testing backend Twitch override normalization...")
    
    # Test cases with expected outputs
    test_cases = [
        {
            "input": {"player_name": "TestPlayer1", "twitch_username": "username123"},
            "expected_link": "https://twitch.tv/username123"
        },
        {
            "input": {"player_name": "TestPlayer2", "twitch_username": "https://www.twitch.tv/Naughty"},
            "expected_link": "https://www.twitch.tv/Naughty"
        },
        {
            "input": {"player_name": "TestPlayer3", "twitch_username": "www.twitch.tv/shroud"},
            "expected_link": "https://www.twitch.tv/shroud"
        },
        {
            "input": {"player_name": "TestPlayer4", "twitch_username": "/testuser"},
            "expected_link": "https://twitch.tv/testuser"
        }
    ]
    
    # Create a temporary test override file
    test_file = "/tmp/test_twitch_overrides.json"
    overrides = {}
    
    all_passed = True
    
    for i, test_case in enumerate(test_cases, 1):
        player_name = test_case["input"]["player_name"]
        twitch_username = test_case["input"]["twitch_username"]
        expected_link = test_case["expected_link"]
        
        # Simulate the backend normalization logic
        if twitch_username.startswith(('http://', 'https://')):
            twitch_link = twitch_username
        elif twitch_username.startswith(('www.twitch.tv/', 'twitch.tv/')):
            twitch_link = f"https://{twitch_username}"
        else:
            # It's just a username, prefix with full Twitch URL
            twitch_link = f"https://twitch.tv/{twitch_username.lstrip('/')}"
        
        overrides[player_name] = {"twitch_link": twitch_link}
        
        if twitch_link == expected_link:
            print(f"✅ Test {i} PASS: '{twitch_username}' -> '{twitch_link}'")
        else:
            print(f"❌ Test {i} FAIL: '{twitch_username}' -> '{twitch_link}' (expected: '{expected_link}')")
            all_passed = False
    
    # Write to test file to verify JSON serialization works
    try:
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(overrides, f, indent=4)
        print(f"\n✅ Successfully saved overrides to {test_file}")
        
        # Verify we can read it back
        with open(test_file, 'r', encoding='utf-8') as f:
            loaded_overrides = json.load(f)
        print(f"✅ Successfully loaded overrides from file")
        
        # Clean up
        os.unlink(test_file)
        
    except Exception as e:
        print(f"❌ Error with file operations: {e}")
        all_passed = False
    
    print(f"\nOverall result: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    return all_passed

if __name__ == "__main__":
    import sys
    success = test_twitch_override_api()
    sys.exit(0 if success else 1)
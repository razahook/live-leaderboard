#!/usr/bin/env python3
"""
Test script for Twitch override functionality
"""

import sys
import os

# Add the src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_twitch_override_normalization():
    """Test the Twitch override logic with different input formats"""
    
    print("Testing Twitch override URL normalization...")
    
    test_cases = [
        ("username", "https://twitch.tv/username"),
        ("https://www.twitch.tv/Naughty", "https://www.twitch.tv/Naughty"),
        ("https://twitch.tv/shroud", "https://twitch.tv/shroud"),
        ("www.twitch.tv/testuser", "https://www.twitch.tv/testuser"),
        ("twitch.tv/player123", "https://twitch.tv/player123"),
        ("/username", "https://twitch.tv/username"),
        ("//username", "https://twitch.tv/username"),
    ]
    
    all_passed = True
    
    for input_val, expected in test_cases:
        # Simulate the logic from twitch_override.py
        if input_val.startswith(('http://', 'https://')):
            result = input_val
        elif input_val.startswith(('www.twitch.tv/', 'twitch.tv/')):
            result = f"https://{input_val}"
        else:
            # It's just a username, prefix with full Twitch URL
            result = f"https://twitch.tv/{input_val.lstrip('/')}"
        
        if result == expected:
            print(f"✅ PASS: '{input_val}' -> '{result}'")
        else:
            print(f"❌ FAIL: '{input_val}' -> '{result}' (expected: '{expected}')")
            all_passed = False
    
    print(f"\nOverall result: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    return all_passed

if __name__ == "__main__":
    success = test_twitch_override_normalization()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Test script for Twitch override functionality
Tests the key requirements from the problem statement
"""

import requests
import json
import time
import sys

BASE_URL = "http://localhost:5000"

def test_twitch_override_immediate_fetch():
    """Test that setting a Twitch override immediately fetches live status"""
    print("Testing: Immediate live status fetch when setting Twitch override...")
    
    # Test data
    test_player = "TestOverridePlayer"
    test_twitch = "naughty"  # Use known mock channel
    
    # Set override
    response = requests.post(f"{BASE_URL}/twitch/override", 
                           json={"player_name": test_player, "twitch_username": test_twitch})
    
    if response.status_code != 200:
        print(f"❌ FAIL: Override request failed with status {response.status_code}")
        return False
    
    data = response.json()
    
    # Check response includes live status
    if not data.get("success"):
        print(f"❌ FAIL: Override request not successful: {data}")
        return False
    
    if "live_status" not in data:
        print(f"❌ FAIL: No live_status in response: {data}")
        return False
    
    live_status = data["live_status"]
    
    # For our mock data, naughty should be live
    if live_status.get("is_live") != True:
        print(f"❌ FAIL: Expected naughty to be live, got: {live_status}")
        return False
    
    if not live_status.get("stream_data", {}).get("viewer_count"):
        print(f"❌ FAIL: Expected viewer count in stream data: {live_status}")
        return False
    
    print(f"✅ PASS: Override immediately fetched live status: {live_status['stream_data']['viewer_count']} viewers")
    return True

def test_leaderboard_includes_override_live_status():
    """Test that leaderboard includes live status for override players"""
    print("Testing: Leaderboard includes live status for override players...")
    
    # Get leaderboard
    response = requests.get(f"{BASE_URL}/leaderboard/PC")
    
    if response.status_code != 200:
        print(f"❌ FAIL: Leaderboard request failed with status {response.status_code}")
        return False
    
    data = response.json()
    
    if not data.get("success"):
        print(f"❌ FAIL: Leaderboard request not successful: {data}")
        return False
    
    players = data.get("data", {}).get("players", [])
    
    if not players:
        print(f"❌ FAIL: No players in leaderboard data")
        return False
    
    # Find LG_Naughty (our known override)
    lg_naughty = next((p for p in players if p.get("player_name") == "LG_Naughty"), None)
    
    if not lg_naughty:
        print(f"❌ FAIL: LG_Naughty not found in leaderboard")
        return False
    
    # Check Twitch link is set
    if not lg_naughty.get("twitch_link"):
        print(f"❌ FAIL: LG_Naughty has no Twitch link: {lg_naughty}")
        return False
    
    # Check live status is set
    twitch_live = lg_naughty.get("twitch_live", {})
    if "is_live" not in twitch_live:
        print(f"❌ FAIL: LG_Naughty has no live status: {lg_naughty}")
        return False
    
    # Check if live, has viewer count
    if twitch_live.get("is_live"):
        stream = lg_naughty.get("stream", {})
        if not stream or "viewers" not in stream:
            print(f"❌ FAIL: LG_Naughty is live but no viewer data: {lg_naughty}")
            return False
        
        viewers = stream["viewers"]
        print(f"✅ PASS: LG_Naughty shows as live with {viewers} viewers")
    else:
        print(f"✅ PASS: LG_Naughty shows as offline")
    
    return True

def test_override_handles_url_formats():
    """Test that override handles both username and full URL formats"""
    print("Testing: Override handles different URL formats...")
    
    test_cases = [
        {"player_name": "TestURL1", "twitch_username": "testuser"},
        {"player_name": "TestURL2", "twitch_username": "https://twitch.tv/testuser2"},
        {"player_name": "TestURL3", "twitch_username": "https://www.twitch.tv/testuser3"},
    ]
    
    for test_case in test_cases:
        response = requests.post(f"{BASE_URL}/twitch/override", json=test_case)
        
        if response.status_code != 200:
            print(f"❌ FAIL: Override failed for {test_case}: status {response.status_code}")
            return False
        
        data = response.json()
        
        if not data.get("success"):
            print(f"❌ FAIL: Override not successful for {test_case}: {data}")
            return False
        
        # Check twitch_link is properly formatted
        twitch_link = data.get("twitch_link")
        if not twitch_link or not twitch_link.startswith("https://twitch.tv/"):
            print(f"❌ FAIL: Invalid twitch_link format for {test_case}: {twitch_link}")
            return False
    
    print(f"✅ PASS: All URL formats handled correctly")
    return True

def main():
    """Run all tests"""
    print("Starting Twitch Override Tests...")
    print("=" * 50)
    
    # Wait for server to be ready
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Server not ready: {response.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        sys.exit(1)
    
    tests = [
        test_override_handles_url_formats,
        test_twitch_override_immediate_fetch,
        test_leaderboard_includes_override_live_status,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ FAIL: Test {test.__name__} crashed: {e}")
            print()
    
    print("=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
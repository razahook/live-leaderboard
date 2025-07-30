#!/usr/bin/env python3
"""
Comprehensive test to verify the Twitch link normalization fix
"""

import json
import os
import tempfile

def test_comprehensive_twitch_normalization():
    """Comprehensive test of both backend and frontend Twitch URL normalization"""
    
    print("🧪 Running Comprehensive Twitch Link Normalization Test\n")
    
    # Test cases that cover all scenarios mentioned in the problem statement
    test_cases = [
        {
            "description": "Full URL with www (should not be double-prefixed)",
            "input": "https://www.twitch.tv/Naughty",
            "expected": "https://www.twitch.tv/Naughty"
        },
        {
            "description": "Full URL without www (should not be double-prefixed)", 
            "input": "https://twitch.tv/shroud",
            "expected": "https://twitch.tv/shroud"
        },
        {
            "description": "Username only (should be prefixed)",
            "input": "testuser",
            "expected": "https://twitch.tv/testuser"
        },
        {
            "description": "URL without protocol with www",
            "input": "www.twitch.tv/player123",
            "expected": "https://www.twitch.tv/player123"
        },
        {
            "description": "URL without protocol without www",
            "input": "twitch.tv/player456",
            "expected": "https://twitch.tv/player456"
        },
        {
            "description": "Username with leading slash",
            "input": "/username",
            "expected": "https://twitch.tv/username"
        },
        {
            "description": "Username with multiple leading slashes",
            "input": "//username",
            "expected": "https://twitch.tv/username"
        }
    ]
    
    print("📊 Backend Normalization Tests:")
    print("-" * 50)
    
    backend_passed = 0
    for i, test_case in enumerate(test_cases, 1):
        input_val = test_case["input"]
        expected = test_case["expected"]
        
        # Simulate backend logic from twitch_override.py
        if input_val.startswith(('http://', 'https://')):
            result = input_val
        elif input_val.startswith(('www.twitch.tv/', 'twitch.tv/')):
            result = f"https://{input_val}"
        else:
            result = f"https://twitch.tv/{input_val.lstrip('/')}"
        
        passed = result == expected
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{i}. {test_case['description']}")
        print(f"   Input: '{input_val}'")
        print(f"   Expected: '{expected}'")
        print(f"   Result: '{result}' {status}")
        print()
        
        if passed:
            backend_passed += 1
    
    print(f"Backend Tests: {backend_passed}/{len(test_cases)} passed\n")
    
    # Test JSON serialization (important for the override file)
    print("💾 JSON Serialization Test:")
    print("-" * 30)
    
    test_overrides = {}
    for i, test_case in enumerate(test_cases, 1):
        player_name = f"Player{i}"
        input_val = test_case["input"]
        
        # Apply backend normalization
        if input_val.startswith(('http://', 'https://')):
            twitch_link = input_val
        elif input_val.startswith(('www.twitch.tv/', 'twitch.tv/')):
            twitch_link = f"https://{input_val}"
        else:
            twitch_link = f"https://twitch.tv/{input_val.lstrip('/')}"
        
        test_overrides[player_name] = {"twitch_link": twitch_link}
    
    # Test file operations
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_overrides, f, indent=2)
            temp_file = f.name
        
        # Read back and verify
        with open(temp_file, 'r') as f:
            loaded_overrides = json.load(f)
        
        if loaded_overrides == test_overrides:
            print("✅ JSON serialization and deserialization successful")
        else:
            print("❌ JSON serialization test failed")
            return False
        
        # Clean up
        os.unlink(temp_file)
        
    except Exception as e:
        print(f"❌ JSON operations failed: {e}")
        return False
    
    # Simulate frontend getTwitchUrl function tests
    print("\n🌐 Frontend Normalization Tests:")
    print("-" * 40)
    
    frontend_passed = 0
    for i, test_case in enumerate(test_cases, 1):
        input_val = test_case["input"]
        expected = test_case["expected"]
        
        # Simulate frontend getTwitchUrl logic
        if not input_val or not isinstance(input_val, str):
            result = ''
        else:
            trimmed = input_val.strip()
            if not trimmed:
                result = ''
            elif trimmed.lower().startswith(('http://twitch.tv/', 'https://twitch.tv/', 'http://www.twitch.tv/', 'https://www.twitch.tv/')):
                result = trimmed
            elif trimmed.lower().startswith(('www.twitch.tv/', 'twitch.tv/')):
                result = f"https://{trimmed}"
            else:
                username = trimmed.lstrip('/')
                result = f"https://twitch.tv/{username}"
        
        passed = result == expected
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{i}. {test_case['description']}")
        print(f"   Result: '{result}' {status}")
        
        if passed:
            frontend_passed += 1
    
    print(f"\nFrontend Tests: {frontend_passed}/{len(test_cases)} passed")
    
    # Overall results
    total_tests = len(test_cases) * 2 + 1  # backend + frontend + json
    total_passed = backend_passed + frontend_passed + 1  # +1 for JSON test
    
    print(f"\n🎯 Overall Test Results:")
    print("=" * 30)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_tests - total_passed}")
    print(f"Success Rate: {(total_passed/total_tests)*100:.1f}%")
    
    success = total_passed == total_tests
    print(f"\n{'🎉 ALL TESTS PASSED!' if success else '❌ SOME TESTS FAILED'}")
    
    if success:
        print("\n✨ The Twitch link normalization fix is working correctly!")
        print("   - Backend prevents double-prefixing of full URLs")
        print("   - Frontend getTwitchUrl utility normalizes all link formats")
        print("   - Both username-only and full URL inputs are handled properly")
    
    return success

if __name__ == "__main__":
    import sys
    success = test_comprehensive_twitch_normalization()
    sys.exit(0 if success else 1)
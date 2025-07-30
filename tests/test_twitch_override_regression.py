#!/usr/bin/env python3
"""
Regression tests for Twitch override live status functionality.

These tests ensure that when a Twitch override is set and the stream is live,
the leaderboard shows 'live' and the correct viewer count.
"""

import json
import sys
import os
import unittest
from unittest.mock import patch

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.index import extract_twitch_username, add_twitch_live_status, load_twitch_overrides

class TestTwitchOverrideLiveStatus(unittest.TestCase):
    """Regression tests for Twitch override live status functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock leaderboard data with players that have overrides
        self.mock_leaderboard_data = {
            "platform": "PC",
            "players": [
                {
                    "rank": 1,
                    "player_name": "LG_Naughty",  # Has override in JSON file
                    "rp": 50000,
                    "rp_change_24h": 100,
                    "twitch_link": "",  # No original link - gets override
                    "level": 500,
                    "status": "In lobby"
                },
                {
                    "rank": 2,
                    "player_name": "RegularPlayer",
                    "rp": 49000,
                    "rp_change_24h": 50,
                    "twitch_link": "https://twitch.tv/regularplayer",  # Original link
                    "level": 450,
                    "status": "Offline"
                }
            ],
            "total_players": 2,
            "last_updated": "2025-01-01T12:00:00"
        }
    
    def test_load_twitch_overrides_from_file(self):
        """Test that Twitch overrides are loaded correctly from JSON file."""
        overrides = load_twitch_overrides()
        self.assertIsInstance(overrides, dict)
        # Should contain LG_Naughty override from the file
        self.assertIn("LG_Naughty", overrides)
        self.assertEqual(overrides["LG_Naughty"]["twitch_link"], "https://www.twitch.tv/Naughty")
    
    def test_username_extraction_various_formats(self):
        """Test username extraction from various Twitch link formats."""
        test_cases = [
            ("https://www.twitch.tv/Naughty", "Naughty"),
            ("https://twitch.tv/Naughty", "Naughty"),
            ("twitch.tv/Naughty", "Naughty"),
            ("apexlegendsstatus.com/core/out?type=twitch&id=Naughty", "Naughty"),
            ("", None),
            (None, None),
            ("https://twitch.tv/TestUser_InMatch", "TestUser"),  # Status suffix removal
            ("https://twitch.tv/TestUser_Offline", "TestUser"),  # Status suffix removal
        ]
        
        for link, expected in test_cases:
            with self.subTest(link=link):
                result = extract_twitch_username(link)
                self.assertEqual(result, expected)
    
    def test_override_application_to_players(self):
        """Test that overrides are correctly applied to player data."""
        leaderboard_data = json.loads(json.dumps(self.mock_leaderboard_data))  # Deep copy
        overrides = load_twitch_overrides()
        
        # Apply overrides like the API does
        for player in leaderboard_data['players']:
            override_info = overrides.get(player.get("player_name"))
            if override_info:
                player["twitch_link"] = override_info["twitch_link"]
                if "display_name" in override_info:
                    player["player_name"] = override_info["display_name"]
        
        # Check that LG_Naughty got the override
        lg_naughty = next(p for p in leaderboard_data['players'] if 'Naughty' in p.get('player_name', '') or p.get('player_name') == 'LG_Naughty')
        self.assertEqual(lg_naughty["twitch_link"], "https://www.twitch.tv/Naughty")
        
        # Check that RegularPlayer kept their original link
        regular_player = next(p for p in leaderboard_data['players'] if p.get('player_name') == 'RegularPlayer')
        self.assertEqual(regular_player["twitch_link"], "https://twitch.tv/regularplayer")
    
    def test_live_status_channel_collection_includes_overrides(self):
        """Test that channels from overrides are included in live status checking."""
        leaderboard_data = json.loads(json.dumps(self.mock_leaderboard_data))  # Deep copy
        overrides = load_twitch_overrides()
        
        # Apply overrides
        for player in leaderboard_data['players']:
            override_info = overrides.get(player.get("player_name"))
            if override_info:
                player["twitch_link"] = override_info["twitch_link"]
                if "display_name" in override_info:
                    player["player_name"] = override_info["display_name"]
        
        # Collect channels like add_twitch_live_status does
        twitch_channels = []
        for player in leaderboard_data['players']:
            if player.get('twitch_link'):
                username = extract_twitch_username(player['twitch_link'])
                if username:
                    twitch_channels.append(username)
        
        # Should include both the override channel and the regular channel
        self.assertIn("Naughty", twitch_channels)  # From override
        self.assertIn("regularplayer", twitch_channels)  # From original link
    
    def test_live_status_applied_to_override_players(self):
        """
        REGRESSION TEST: When a Twitch override is set and the stream is live,
        the leaderboard shows 'live' and the correct viewer count.
        """
        leaderboard_data = json.loads(json.dumps(self.mock_leaderboard_data))  # Deep copy
        overrides = load_twitch_overrides()
        
        # Apply overrides
        for player in leaderboard_data['players']:
            override_info = overrides.get(player.get("player_name"))
            if override_info:
                player["twitch_link"] = override_info["twitch_link"]
                if "display_name" in override_info:
                    player["player_name"] = override_info["display_name"]
        
        # Mock live status (simulate Twitch API response)
        mock_live_status = {
            "naughty": {  # Note: lowercase (API response format)
                "is_live": True,
                "stream_data": {
                    "title": "Apex Ranked Grind",
                    "game_name": "Apex Legends",
                    "viewer_count": 2500,
                    "started_at": "2025-01-01T12:00:00Z",
                    "thumbnail_url": "https://mock.twitch.tv/thumbnail.jpg",
                    "user_name": "Naughty"
                }
            },
            "regularplayer": {  # Note: lowercase
                "is_live": False,
                "stream_data": None
            }
        }
        
        # Mock the get_twitch_live_status function to return our test data
        with patch('api.index.get_twitch_live_status', return_value=mock_live_status):
            # Apply live status
            leaderboard_data = add_twitch_live_status(leaderboard_data)
        
        # VERIFICATION: Check that overridden player shows live status correctly
        lg_naughty = next(p for p in leaderboard_data['players'] if 'Naughty' in p.get('player_name', '') or p.get('player_name') == 'LG_Naughty')
        
        # These are the key assertions that verify the bug is fixed:
        self.assertTrue(lg_naughty['twitch_live']['is_live'], 
                       "LG_Naughty should show as live when override stream is live")
        self.assertEqual(lg_naughty['stream']['viewers'], 2500, 
                        "LG_Naughty should show correct viewer count from override stream")
        self.assertEqual(lg_naughty['stream']['twitchUser'], "Naughty", 
                        "LG_Naughty should show correct Twitch username from override")
        self.assertEqual(lg_naughty['stream']['game'], "Apex Legends", 
                        "LG_Naughty should show correct game from override stream")
        
        # Check that regular player works normally
        regular_player = next(p for p in leaderboard_data['players'] if p.get('player_name') == 'RegularPlayer')
        self.assertFalse(regular_player['twitch_live']['is_live'], 
                        "RegularPlayer should show as offline when not live")
        self.assertIsNone(regular_player['stream'], 
                         "RegularPlayer should have no stream data when offline")
    
    def test_case_sensitivity_in_live_status_lookup(self):
        """
        Test that case sensitivity doesn't break live status lookup.
        The extract_twitch_username returns "Naughty" but API returns lowercase "naughty".
        """
        # Test data with mixed case
        test_player = {
            "player_name": "TestPlayer",
            "twitch_link": "https://www.twitch.tv/TestUser",  # Capital T
            "rank": 1,
            "rp": 10000,
            "rp_change_24h": 0,
            "level": 100,
            "status": "Online"
        }
        
        leaderboard_data = {
            "platform": "PC",
            "players": [test_player],
            "total_players": 1,
            "last_updated": "2025-01-01T12:00:00"
        }
        
        # Mock live status with lowercase username (as API would return)
        mock_live_status = {
            "testuser": {  # lowercase
                "is_live": True,
                "stream_data": {
                    "title": "Test Stream",
                    "game_name": "Apex Legends",
                    "viewer_count": 100,
                    "started_at": "2025-01-01T12:00:00Z",
                    "thumbnail_url": "https://mock.twitch.tv/thumbnail.jpg",
                    "user_name": "TestUser"
                }
            }
        }
        
        with patch('api.index.get_twitch_live_status', return_value=mock_live_status):
            result = add_twitch_live_status(leaderboard_data)
        
        # Should find the live status despite case difference
        player = result['players'][0]
        self.assertTrue(player['twitch_live']['is_live'], 
                       "Live status lookup should work despite case differences")
        self.assertEqual(player['stream']['viewers'], 100, 
                        "Viewer count should be retrieved despite case differences")

if __name__ == "__main__":
    # Run the tests
    unittest.main(verbosity=2)
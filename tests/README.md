# Tests

This directory contains regression tests for the live-leaderboard application.

## Running Tests

To run all tests:
```bash
python tests/test_twitch_override_regression.py
```

## Test Coverage

### `test_twitch_override_regression.py`
Regression tests for the Twitch override live status functionality. These tests ensure that when a Twitch override is set and the stream is live, the leaderboard shows 'live' and the correct viewer count.

**Key Test Cases:**
- `test_live_status_applied_to_override_players`: The main regression test that verifies overridden players show live status and viewer count correctly
- `test_case_sensitivity_in_live_status_lookup`: Ensures case sensitivity doesn't break live status lookup
- `test_override_application_to_players`: Verifies overrides are applied correctly to player data
- `test_load_twitch_overrides_from_file`: Tests loading overrides from JSON file
- `test_username_extraction_various_formats`: Tests username extraction from various Twitch URL formats
- `test_live_status_channel_collection_includes_overrides`: Verifies override channels are included in live status checks

## Bug Fixed

The main bug that was fixed: When a Twitch override was set (e.g., LG_Naughty -> https://www.twitch.tv/Naughty), the leaderboard would show the override link but not the live indicator or viewer count. This was caused by:

1. `load_twitch_overrides()` not reading from the JSON file
2. Case sensitivity mismatch in live status lookup

The tests in this directory ensure this bug doesn't regress.
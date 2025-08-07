from flask import Blueprint, jsonify
import sys
import os

twitch_import_debug_bp = Blueprint('twitch_import_debug', __name__)

@twitch_import_debug_bp.route('/debug/import-check', methods=['GET'])
def debug_import_check():
    """Check if Twitch integration imports work in leaderboard scraper"""
    try:
        # Check what's actually available
        available_modules = []
        import_errors = {}
        
        # Test individual imports
        try:
            from routes.twitch_integration import extract_twitch_username, get_twitch_access_token, get_twitch_live_status_batch
            available_modules.append("twitch_integration")
            
            # Test the functions work
            test_username = extract_twitch_username("https://www.twitch.tv/testuser")
            token = get_twitch_access_token()
            
            return jsonify({
                "success": True,
                "twitch_integration_available": True,
                "extract_username_test": test_username,
                "token_available": token is not None,
                "token_length": len(token) if token else 0,
                "available_modules": available_modules,
                "python_path": sys.path[:3],
                "current_dir": os.getcwd()
            })
            
        except ImportError as e:
            import_errors["twitch_integration"] = str(e)
        except Exception as e:
            import_errors["function_test"] = str(e)
            
        # Test leaderboard scraper imports
        try:
            from routes.leaderboard_scraper import scrape_leaderboard
            available_modules.append("leaderboard_scraper")
        except ImportError as e:
            import_errors["leaderboard_scraper"] = str(e)
            
        return jsonify({
            "success": False,
            "twitch_integration_available": False,
            "available_modules": available_modules,
            "import_errors": import_errors,
            "python_path": sys.path[:3],
            "current_dir": os.getcwd()
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        })
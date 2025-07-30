import os
import sys
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime

# CORRECTED: This now correctly adds the project's root directory to the path,
# allowing it to find the 'src' folder and all its contents.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Import all of your blueprints from your 'src/routes' folder
# from src.routes.user import user_bp  # Temporarily disabled due to missing models
from src.routes.apex_scraper import apex_scraper_bp
from src.routes.leaderboard_scraper import leaderboard_bp
from src.routes.twitch_integration import twitch_bp
from src.routes.twitch_override import twitch_override_bp
from src.routes.tracker_proxy import tracker_proxy_bp

# CORRECTED: This now imports your database initializer from the correct src/user.py file
# from src.user import init_app as init_db  # Temporarily disabled due to missing models

# This is the single Flask app Vercel will run
app = Flask(__name__)
CORS(app)

# Simple health check endpoint
@app.route('/health', methods=['GET'])
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })

# Initialize the database connection
# init_db(app)  # Temporarily disabled due to missing models

# Register all of your blueprints on this single app
# app.register_blueprint(user_bp)  # Temporarily disabled due to missing models
app.register_blueprint(apex_scraper_bp)
app.register_blueprint(leaderboard_bp)
app.register_blueprint(twitch_bp)
app.register_blueprint(twitch_override_bp)
app.register_blueprint(tracker_proxy_bp)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

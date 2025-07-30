from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.routes.twitch_override import twitch_override_bp
from src.routes.leaderboard_scraper import leaderboard_bp

app = Flask(__name__)
CORS(app)

# Register only the blueprints we need for testing
app.register_blueprint(twitch_override_bp, url_prefix='/api')
app.register_blueprint(leaderboard_bp, url_prefix='/api')

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": "2025-07-30T00:00:00.000000",
        "version": "1.0.0"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
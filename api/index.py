import os
from flask import Flask
from flask_cors import CORS

from src.routes.leaderboard_scraper import leaderboard_bp
from src.routes.apex_scraper import apex_scraper_bp
from src.routes.tracker_proxy import tracker_proxy_bp
from src.routes.twitch_integration import twitch_bp
from src.routes.twitch_override import twitch_override_bp
from src.routes.user import user_bp

def create_app():
    app = Flask(__name__)
    CORS(app)

    # Register all blueprints at the /api/ path
    app.register_blueprint(leaderboard_bp, url_prefix='/api')
    app.register_blueprint(apex_scraper_bp, url_prefix='/api')
    app.register_blueprint(tracker_proxy_bp, url_prefix='/api')
    app.register_blueprint(twitch_bp, url_prefix='/api')
    app.register_blueprint(twitch_override_bp, url_prefix='/api')
    app.register_blueprint(user_bp, url_prefix='/api')

    @app.route('/api/health', methods=['GET'])
    def health():
        from datetime import datetime
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        }

    return app

# This is required for Vercel: expose the app variable
app = create_app()
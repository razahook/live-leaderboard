import os
import sys
from flask import Flask
from flask_cors import CORS

# This robustly adds the project root to the path so it can find 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import all of your blueprints from your 'src/routes' folder
from src.routes.user import user_bp
from src.routes.apex_scraper import apex_scraper_bp
from src.routes.leaderboard_scraper import leaderboard_bp
from src.routes.twitch_integration import twitch_bp
from src.routes.twitch_override import twitch_override_bp
from src.routes.tracker_proxy import tracker_proxy_bp

# Import your database initializer
from src.models import init_app as init_db

# This is the single Flask app Vercel will run
app = Flask(__name__)
CORS(app)

# Initialize the database connection
init_db(app)

# Register all of your blueprints on this single app
app.register_blueprint(user_bp)
app.register_blueprint(apex_scraper_bp)
app.register_blueprint(leaderboard_bp)
app.register_blueprint(twitch_bp)
app.register_blueprint(twitch_override_bp)
app.register_blueprint(tracker_proxy_bp)

# Note: There is no app.run(). Vercel handles this.

from flask import Flask
from flask_cors import CORS

# Import all of your blueprints from your new structure
from scrapers.user import user_bp
from scrapers.apex_scraper import apex_scraper_bp
from scrapers.leaderboard_scraper import leaderboard_bp
from scrapers.twitch_integration import twitch_bp
from scrapers.twitch_override import twitch_override_bp
from scrapers.tracker_proxy import tracker_proxy_bp

# Import your database initializer from the api directory
from user import init_app as init_db

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

# This is what Vercel will call
def handler(request):
    return app(request.environ, lambda status, headers: None)
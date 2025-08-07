import os
import sys
from dotenv import load_dotenv
from flask import Flask, send_from_directory, jsonify, request, send_file
from flask_cors import CORS
from functools import wraps
import time
import logging
from collections import defaultdict

# Load environment variables
load_dotenv()

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from models.user import db
from routes.user import user_bp
from routes.apex_scraper import apex_scraper_bp
from routes.leaderboard_scraper import leaderboard_bp
from routes.twitch_integration import twitch_bp
from routes.twitch_override import twitch_override_bp
from routes.tracker_proxy import tracker_proxy_bp
from routes.twitch_clips import twitch_clips_bp
from routes.twitch_vod_downloader import twitch_vod_bp
from routes.twitch_hidden_vods import twitch_hidden_vods_bp
from routes.twitch_live_rewind import twitch_live_rewind_bp
from routes.twitch_oauth import twitch_oauth_bp

# Import QoL improvement modules
from routes.user_preferences import user_preferences_bp
from routes.health import health_bp
from routes.analytics import analytics_bp
from routes.webhooks import webhooks_bp

# Create Flask app - no static folder needed since Vercel handles static files
app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'test-secret-key')

# Enable CORS
CORS(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple rate limiting
rate_limits = defaultdict(list)

def rate_limit(max_requests=60, window=60):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
            current_time = time.time()
            
            # Clean old requests
            rate_limits[client_ip] = [t for t in rate_limits[client_ip] if current_time - t < window]
            
            # Check rate limit
            if len(rate_limits[client_ip]) >= max_requests:
                return jsonify({'error': 'Rate limit exceeded'}), 429
            
            # Add current request
            rate_limits[client_ip].append(current_time)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Database configuration
database_path = os.path.join(os.path.dirname(__file__), 'database', 'test_app.db')
os.makedirs(os.path.dirname(database_path), exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Register blueprints with API prefix
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(apex_scraper_bp, url_prefix='/api') 
app.register_blueprint(leaderboard_bp, url_prefix='/api')
app.register_blueprint(twitch_bp, url_prefix='/api')
app.register_blueprint(twitch_override_bp, url_prefix='/api')
app.register_blueprint(tracker_proxy_bp, url_prefix='/api')
app.register_blueprint(twitch_clips_bp, url_prefix='/api')
app.register_blueprint(twitch_vod_bp, url_prefix='/api')
app.register_blueprint(twitch_hidden_vods_bp, url_prefix='/api')
app.register_blueprint(twitch_live_rewind_bp, url_prefix='/api')
app.register_blueprint(twitch_oauth_bp, url_prefix='/api')

# Register QoL improvement blueprints
app.register_blueprint(user_preferences_bp, url_prefix='/api')
app.register_blueprint(health_bp, url_prefix='/api')
app.register_blueprint(analytics_bp, url_prefix='/api')
app.register_blueprint(webhooks_bp, url_prefix='/api')

# Serve the main HTML file at root
@app.route('/')
def index():
    """Serve the main HTML file"""
    try:
        return send_file('index.html')
    except Exception as e:
        logger.error(f"Error serving index.html: {e}")
        return jsonify({'error': 'Frontend not found'}), 404

# Serve static files
@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files"""
    try:
        return send_from_directory('static', filename)
    except Exception as e:
        logger.error(f"Error serving static file {filename}: {e}")
        return jsonify({'error': 'File not found'}), 404

# Health check endpoint
@app.route('/health')
def health_check():
    """Simple health check"""
    return jsonify({
        'status': 'healthy',
        'message': 'Apex Legends Leaderboard API is running',
        'timestamp': time.time()
    })

# Create database tables
with app.app_context():
    try:
        db.create_all()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

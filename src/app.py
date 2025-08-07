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

# Set up logging FIRST
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

# Try to import database models (may fail in Vercel)
try:
    from models.user import db
    DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Database models not available: {e}")
    DB_AVAILABLE = False
    db = None

# Import route modules with error handling
imported_blueprints = []

try:
    from routes.user import user_bp
    imported_blueprints.append(('user_bp', user_bp))
except ImportError as e:
    logger.warning(f"Could not import user routes: {e}")

try:
    from routes.apex_scraper import apex_scraper_bp
    imported_blueprints.append(('apex_scraper_bp', apex_scraper_bp))
except ImportError as e:
    logger.warning(f"Could not import apex_scraper routes: {e}")

try:
    from routes.leaderboard_scraper import leaderboard_bp
    imported_blueprints.append(('leaderboard_bp', leaderboard_bp))
except ImportError as e:
    logger.warning(f"Could not import leaderboard routes: {e}")

try:
    from routes.twitch_integration import twitch_bp
    imported_blueprints.append(('twitch_bp', twitch_bp))
except ImportError as e:
    logger.warning(f"Could not import twitch_integration routes: {e}")

try:
    from routes.twitch_override import twitch_override_bp
    imported_blueprints.append(('twitch_override_bp', twitch_override_bp))
except ImportError as e:
    logger.warning(f"Could not import twitch_override routes: {e}")

try:
    from routes.tracker_proxy import tracker_proxy_bp
    imported_blueprints.append(('tracker_proxy_bp', tracker_proxy_bp))
except ImportError as e:
    logger.warning(f"Could not import tracker_proxy routes: {e}")

try:
    from routes.twitch_clips import twitch_clips_bp
    imported_blueprints.append(('twitch_clips_bp', twitch_clips_bp))
except ImportError as e:
    logger.warning(f"Could not import twitch_clips routes: {e}")

try:
    from routes.twitch_vod_downloader import twitch_vod_bp
    imported_blueprints.append(('twitch_vod_bp', twitch_vod_bp))
except ImportError as e:
    logger.warning(f"Could not import twitch_vod_downloader routes: {e}")

try:
    from routes.twitch_hidden_vods import twitch_hidden_vods_bp
    imported_blueprints.append(('twitch_hidden_vods_bp', twitch_hidden_vods_bp))
except ImportError as e:
    logger.warning(f"Could not import twitch_hidden_vods routes: {e}")

try:
    from routes.twitch_live_rewind import twitch_live_rewind_bp
    imported_blueprints.append(('twitch_live_rewind_bp', twitch_live_rewind_bp))
except ImportError as e:
    logger.warning(f"Could not import twitch_live_rewind routes: {e}")

try:
    from routes.twitch_oauth import twitch_oauth_bp
    imported_blueprints.append(('twitch_oauth_bp', twitch_oauth_bp))
except ImportError as e:
    logger.warning(f"Could not import twitch_oauth routes: {e}")

try:
    from routes.user_preferences import user_preferences_bp
    imported_blueprints.append(('user_preferences_bp', user_preferences_bp))
except ImportError as e:
    logger.warning(f"Could not import user_preferences routes: {e}")

try:
    from routes.health import health_bp
    imported_blueprints.append(('health_bp', health_bp))
except ImportError as e:
    logger.warning(f"Could not import health routes: {e}")

try:
    from routes.analytics import analytics_bp
    imported_blueprints.append(('analytics_bp', analytics_bp))
except ImportError as e:
    logger.warning(f"Could not import analytics routes: {e}")

try:
    from routes.webhooks import webhooks_bp
    imported_blueprints.append(('webhooks_bp', webhooks_bp))
except ImportError as e:
    logger.warning(f"Could not import webhooks routes: {e}")

try:
    from routes.twitch_debug import twitch_debug_bp
    imported_blueprints.append(('twitch_debug_bp', twitch_debug_bp))
except ImportError as e:
    logger.warning(f"Could not import twitch_debug routes: {e}")

try:
    from routes.twitch_debug_override_test import twitch_debug_override_bp
    imported_blueprints.append(('twitch_debug_override_bp', twitch_debug_override_bp))
except ImportError as e:
    logger.warning(f"Could not import twitch_debug_override_test routes: {e}")

# Create Flask app - no static folder needed since Vercel handles static files
app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'test-secret-key')

# Enable CORS
CORS(app)

# Logging already set up above

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

# Database configuration (only if available) - handle Vercel read-only filesystem
if DB_AVAILABLE and db:
    try:
        # Detect Vercel or serverless environment
        current_dir = os.path.dirname(__file__)
        is_serverless = any([
            os.environ.get('VERCEL'),
            os.environ.get('AWS_LAMBDA_FUNCTION_NAME'),  # AWS Lambda  
            os.environ.get('VERCEL_ENV'),  # Vercel specific
            '/var/task' in current_dir,  # Lambda runtime path
            '/tmp' in current_dir,  # Common serverless temp directory
        ])
        
        logger.info(f"Serverless detection: VERCEL={os.environ.get('VERCEL')}, current_dir={current_dir}, is_serverless={is_serverless}")
        logger.info("Deployment timestamp: 2025-08-07 10:30 - All fixes applied")
        
        # Additional check for read-only filesystem
        if not is_serverless:
            try:
                test_path = os.path.join(os.path.dirname(__file__), 'test_write')
                with open(test_path, 'w') as f:
                    f.write('test')
                os.remove(test_path)
            except (OSError, PermissionError):
                is_serverless = True  # Filesystem is read-only
        
        if is_serverless:
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
            logger.info("Detected serverless environment - using in-memory database")
        else:
            # Use file-based database for local development
            database_path = os.path.join(os.path.dirname(__file__), 'database', 'test_app.db')
            try:
                os.makedirs(os.path.dirname(database_path), exist_ok=True)
                app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path}'
                logger.info(f"Using file-based database: {database_path}")
            except (OSError, PermissionError) as e:
                logger.warning(f"Cannot create database directory: {e}, falling back to in-memory")
                app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(app)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        DB_AVAILABLE = False
        db = None
else:
    logger.warning("Database not available - running without persistence")

# Register successfully imported blueprints
logger.info(f"Registering {len(imported_blueprints)} blueprints")
for blueprint_name, blueprint in imported_blueprints:
    try:
        app.register_blueprint(blueprint, url_prefix='/api')
        logger.info(f"Registered blueprint: {blueprint_name}")
    except Exception as e:
        logger.error(f"Failed to register blueprint {blueprint_name}: {e}")

# Add a simple root route for health checking
@app.route('/api/status')
def api_status():
    """API status endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'API is running',
        'blueprints_loaded': len(imported_blueprints),
        'database_available': DB_AVAILABLE
    })

# Health check endpoint
@app.route('/api/health')
def health_check():
    """Simple health check"""
    return jsonify({
        'status': 'healthy',
        'message': 'Apex Legends Leaderboard API is running',
        'timestamp': time.time(),
        'blueprints_loaded': [name for name, _ in imported_blueprints]
    })

# Create database tables (only if database is available)
if DB_AVAILABLE and db:
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
else:
    logger.info("Skipping database table creation - database not available")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

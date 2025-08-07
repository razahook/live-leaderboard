from flask import Blueprint, jsonify
from models.user import db
import os
import time
import requests
from datetime import datetime, timedelta
import logging

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

health_bp = Blueprint('health', __name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Comprehensive health check for all system components"""
    start_time = time.time()
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'checks': {},
        'response_time_ms': 0
    }
    
    overall_healthy = True
    
    # Database connectivity check
    db_check = _check_database()
    health_status['checks']['database'] = db_check
    if not db_check['healthy']:
        overall_healthy = False
    
    # Twitch API check
    twitch_check = _check_twitch_api()
    health_status['checks']['twitch_api'] = twitch_check
    if not twitch_check['healthy']:
        overall_healthy = False
    
    # Cache system check
    cache_check = _check_cache_system()
    health_status['checks']['cache_system'] = cache_check
    if not cache_check['healthy']:
        overall_healthy = False
    
    # Disk space check
    disk_check = _check_disk_space()
    health_status['checks']['disk_space'] = disk_check
    if not disk_check['healthy']:
        overall_healthy = False
    
    # Memory usage check
    memory_check = _check_memory_usage()
    health_status['checks']['memory'] = memory_check
    if not memory_check['healthy']:
        overall_healthy = False
    
    # Environment variables check
    env_check = _check_environment_variables()
    health_status['checks']['environment'] = env_check
    if not env_check['healthy']:
        overall_healthy = False
    
    # Calculate response time
    health_status['response_time_ms'] = round((time.time() - start_time) * 1000, 2)
    
    # Set overall status
    if overall_healthy:
        health_status['status'] = 'healthy'
        status_code = 200
    else:
        health_status['status'] = 'unhealthy'
        status_code = 503
    
    # Log health check result
    logger.info(f"Health check completed: {health_status['status']} in {health_status['response_time_ms']}ms")
    
    return jsonify(health_status), status_code

@health_bp.route('/health/database', methods=['GET'])
def health_check_database():
    """Detailed database health check"""
    return jsonify(_check_database()), 200

@health_bp.route('/health/twitch', methods=['GET'])
def health_check_twitch():
    """Detailed Twitch API health check"""
    return jsonify(_check_twitch_api()), 200

@health_bp.route('/health/cache', methods=['GET'])
def health_check_cache():
    """Detailed cache system health check"""
    return jsonify(_check_cache_system()), 200

def _check_database():
    """Check database connectivity and basic operations"""
    check_result = {
        'healthy': False,
        'message': '',
        'details': {},
        'timestamp': datetime.utcnow().isoformat()
    }
    
    try:
        # Test basic connection
        start_time = time.time()
        result = db.engine.execute('SELECT 1').scalar()
        connection_time = round((time.time() - start_time) * 1000, 2)
        
        if result == 1:
            # Test table existence
            from models.user import User, UserPreferences
            user_count = User.query.count()
            prefs_count = UserPreferences.query.count()
            
            check_result.update({
                'healthy': True,
                'message': 'Database is healthy',
                'details': {
                    'connection_time_ms': connection_time,
                    'user_count': user_count,
                    'preferences_count': prefs_count,
                    'database_url': db.engine.url.database if hasattr(db.engine.url, 'database') else 'unknown'
                }
            })
        else:
            check_result['message'] = 'Database connection test failed'
            
    except Exception as e:
        check_result.update({
            'message': f'Database error: {str(e)}',
            'details': {'error_type': type(e).__name__}
        })
        logger.error(f"Database health check failed: {str(e)}")
    
    return check_result

def _check_twitch_api():
    """Check Twitch API connectivity and authentication"""
    check_result = {
        'healthy': False,
        'message': '',
        'details': {},
        'timestamp': datetime.utcnow().isoformat()
    }
    
    try:
        # Check environment variables
        client_id = os.environ.get('TWITCH_CLIENT_ID')
        client_secret = os.environ.get('TWITCH_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            check_result.update({
                'message': 'Twitch API credentials not configured',
                'details': {
                    'client_id_set': bool(client_id),
                    'client_secret_set': bool(client_secret)
                }
            })
            return check_result
        
        # Test getting access token
        start_time = time.time()
        try:
            from routes.twitch_integration import get_twitch_access_token
            token = get_twitch_access_token()
            token_time = round((time.time() - start_time) * 1000, 2)
            
            if not token:
                check_result.update({
                    'message': 'Failed to obtain Twitch access token',
                    'details': {'token_request_time_ms': token_time}
                })
                return check_result
        except ImportError:
            check_result.update({
                'message': 'Twitch integration module not available',
                'details': {'import_error': True}
            })
            return check_result
        
        # Test API call
        api_start_time = time.time()
        headers = {
            'Client-Id': client_id,
            'Authorization': f'Bearer {token}'
        }
        
        response = requests.get(
            'https://api.twitch.tv/helix/streams?first=1',
            headers=headers,
            timeout=10
        )
        api_time = round((time.time() - api_start_time) * 1000, 2)
        
        if response.status_code == 200:
            check_result.update({
                'healthy': True,
                'message': 'Twitch API is healthy',
                'details': {
                    'token_request_time_ms': token_time,
                    'api_request_time_ms': api_time,
                    'api_response_status': response.status_code,
                    'rate_limit_remaining': response.headers.get('ratelimit-remaining', 'unknown'),
                    'rate_limit_reset': response.headers.get('ratelimit-reset', 'unknown')
                }
            })
        else:
            check_result.update({
                'message': f'Twitch API returned status {response.status_code}',
                'details': {
                    'api_response_status': response.status_code,
                    'api_response_text': response.text[:200],  # First 200 chars
                    'api_request_time_ms': api_time
                }
            })
            
    except requests.Timeout:
        check_result.update({
            'message': 'Twitch API request timed out',
            'details': {'timeout': True}
        })
    except Exception as e:
        check_result.update({
            'message': f'Twitch API error: {str(e)}',
            'details': {'error_type': type(e).__name__}
        })
        logger.error(f"Twitch API health check failed: {str(e)}")
    
    return check_result

def _check_cache_system():
    """Check cache system health"""
    check_result = {
        'healthy': False,
        'message': '',
        'details': {},
        'timestamp': datetime.utcnow().isoformat()
    }
    
    try:
        # Check cache directory
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache')
        cache_exists = os.path.exists(cache_dir)
        
        if not cache_exists:
            check_result.update({
                'message': 'Cache directory does not exist',
                'details': {'cache_directory': cache_dir, 'exists': False}
            })
            return check_result
        
        # Check cache subdirectories
        twitch_cache_dir = os.path.join(cache_dir, 'twitch')
        twitch_cache_exists = os.path.exists(twitch_cache_dir)
        
        # Check cache files
        cache_files = {}
        if twitch_cache_exists:
            for cache_file in ['access_tokens.json', 'user_validation.json', 'clips.json', 'vods.json']:
                file_path = os.path.join(twitch_cache_dir, cache_file)
                file_exists = os.path.exists(file_path)
                file_size = os.path.getsize(file_path) if file_exists else 0
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat() if file_exists else None
                
                cache_files[cache_file] = {
                    'exists': file_exists,
                    'size_bytes': file_size,
                    'last_modified': file_mtime
                }
        
        # Check in-memory cache
        try:
            from cache_manager import leaderboard_cache
            memory_cache_status = {
                'has_data': leaderboard_cache.data is not None,
                'last_updated': leaderboard_cache.last_updated.isoformat() if leaderboard_cache.last_updated else None,
                'is_expired': leaderboard_cache.is_expired(),
                'cache_duration': leaderboard_cache.cache_duration
            }
        except ImportError:
            memory_cache_status = {'error': 'Cache manager not available'}
        
        check_result.update({
            'healthy': True,
            'message': 'Cache system is healthy',
            'details': {
                'cache_directory': cache_dir,
                'twitch_cache_directory': twitch_cache_dir,
                'cache_files': cache_files,
                'memory_cache': memory_cache_status
            }
        })
        
    except Exception as e:
        check_result.update({
            'message': f'Cache system error: {str(e)}',
            'details': {'error_type': type(e).__name__}
        })
        logger.error(f"Cache system health check failed: {str(e)}")
    
    return check_result

def _check_disk_space():
    """Check available disk space"""
    check_result = {
        'healthy': True,
        'message': 'Disk space is healthy',
        'details': {},
        'timestamp': datetime.utcnow().isoformat()
    }
    
    try:
        import shutil
        
        # Check disk usage for the application directory
        app_dir = os.path.dirname(os.path.dirname(__file__))
        total, used, free = shutil.disk_usage(app_dir)
        
        # Convert to GB
        total_gb = round(total / (1024**3), 2)
        used_gb = round(used / (1024**3), 2)
        free_gb = round(free / (1024**3), 2)
        used_percent = round((used / total) * 100, 2)
        
        # Check if disk usage is concerning (>90% used or <1GB free)
        if used_percent > 90 or free_gb < 1:
            check_result.update({
                'healthy': False,
                'message': 'Low disk space warning'
            })
        
        check_result['details'] = {
            'total_gb': total_gb,
            'used_gb': used_gb,
            'free_gb': free_gb,
            'used_percent': used_percent,
            'path': app_dir
        }
        
    except Exception as e:
        check_result.update({
            'healthy': False,
            'message': f'Disk space check error: {str(e)}',
            'details': {'error_type': type(e).__name__}
        })
    
    return check_result

def _check_memory_usage():
    """Check memory usage (basic check)"""
    check_result = {
        'healthy': True,
        'message': 'Memory usage is healthy',
        'details': {},
        'timestamp': datetime.utcnow().isoformat()
    }
    
    try:
        if not PSUTIL_AVAILABLE:
            check_result.update({
                'message': 'Memory check not available (psutil not installed)',
                'details': {'psutil_available': False}
            })
            return check_result
        
        # Get system memory info
        memory = psutil.virtual_memory()
        
        memory_percent = memory.percent
        available_gb = round(memory.available / (1024**3), 2)
        
        # Check if memory usage is concerning (>90% used)
        if memory_percent > 90:
            check_result.update({
                'healthy': False,
                'message': 'High memory usage warning'
            })
        
        check_result['details'] = {
            'total_gb': round(memory.total / (1024**3), 2),
            'available_gb': available_gb,
            'used_percent': memory_percent
        }
        
    except Exception as e:
        check_result.update({
            'healthy': False,
            'message': f'Memory usage check error: {str(e)}',
            'details': {'error_type': type(e).__name__}
        })
    
    return check_result

def _check_environment_variables():
    """Check critical environment variables"""
    check_result = {
        'healthy': True,
        'message': 'Environment variables are properly configured',
        'details': {},
        'timestamp': datetime.utcnow().isoformat()
    }
    
    required_vars = [
        'TWITCH_CLIENT_ID',
        'TWITCH_CLIENT_SECRET'
    ]
    
    optional_vars = [
        'TRACKER_GG_API_KEY',
        'APEX_API_KEY',
        'SECRET_KEY'
    ]
    
    missing_required = []
    missing_optional = []
    
    for var in required_vars:
        if not os.environ.get(var):
            missing_required.append(var)
    
    for var in optional_vars:
        if not os.environ.get(var):
            missing_optional.append(var)
    
    if missing_required:
        check_result.update({
            'healthy': False,
            'message': f'Missing required environment variables: {", ".join(missing_required)}'
        })
    
    check_result['details'] = {
        'required_vars_set': len(required_vars) - len(missing_required),
        'required_vars_total': len(required_vars),
        'missing_required': missing_required,
        'optional_vars_set': len(optional_vars) - len(missing_optional),
        'optional_vars_total': len(optional_vars),
        'missing_optional': missing_optional
    }
    
    return check_result
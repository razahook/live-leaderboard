from flask import Blueprint, jsonify
import os
import sys
import time
import requests
from datetime import datetime, timedelta
import logging

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Basic health check for Vercel deployment"""
    start_time = time.time()
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'checks': {},
        'response_time_ms': 0
    }
    
    overall_healthy = True
    
    # Basic API check
    health_status['checks']['api'] = {
        'healthy': True,
        'message': 'API responding normally',
        'timestamp': datetime.utcnow().isoformat()
    }
    
    # Environment check
    health_status['checks']['environment'] = {
        'healthy': True,
        'message': 'Vercel serverless environment',
        'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        'timestamp': datetime.utcnow().isoformat()
    }
    
    # System resources (if available)
    if PSUTIL_AVAILABLE:
        try:
            health_status['checks']['system'] = {
                'healthy': True,
                'message': 'System resources available',
                'memory_percent': psutil.virtual_memory().percent,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            health_status['checks']['system'] = {
                'healthy': False,
                'message': f'System check failed: {str(e)}',
                'timestamp': datetime.utcnow().isoformat()
            }
            overall_healthy = False
    else:
        health_status['checks']['system'] = {
            'healthy': True,
            'message': 'psutil not available (normal for serverless)',
            'timestamp': datetime.utcnow().isoformat()
        }
    
    # Set overall status
    health_status['status'] = 'healthy' if overall_healthy else 'unhealthy'
    health_status['response_time_ms'] = round((time.time() - start_time) * 1000, 2)
    
    status_code = 200 if overall_healthy else 503
    return jsonify(health_status), status_code

@health_bp.route('/ping', methods=['GET'])
def ping():
    """Simple ping endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat(),
        'message': 'pong'
    })

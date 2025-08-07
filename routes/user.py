from flask import Blueprint, jsonify, request
from models.user import User, db
import re
from sqlalchemy.exc import IntegrityError
from functools import wraps
import time
from collections import defaultdict

# Import rate limiting from main (simple version)
rate_limits = defaultdict(list)

def rate_limit(max_requests=60, window=60):
    """Simple rate limiting decorator"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
            now = time.time()
            
            # Clean old requests
            rate_limits[client_ip] = [req_time for req_time in rate_limits[client_ip] if now - req_time < window]
            
            # Check rate limit
            if len(rate_limits[client_ip]) >= max_requests:
                return jsonify({"success": False, "message": "Rate limit exceeded"}), 429
            
            # Add current request
            rate_limits[client_ip].append(now)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

user_bp = Blueprint('user', __name__)

@user_bp.route('/users', methods=['GET'])
@rate_limit(max_requests=20, window=60)  # 20 requests per minute for listing users
def get_users():
    users = User.query.all()
    return jsonify([user.to_dict() for user in users])

def validate_user_data(data):
    """Validate user input data"""
    if not data:
        return False, "No data provided"
    
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    
    # Validate username
    if not username or len(username) < 3 or len(username) > 80:
        return False, "Username must be 3-80 characters"
    
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Username can only contain letters, numbers, underscores, and hyphens"
    
    # Validate email
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not email or not re.match(email_pattern, email):
        return False, "Invalid email format"
    
    if len(email) > 120:
        return False, "Email must be less than 120 characters"
    
    return True, {"username": username, "email": email}

@user_bp.route('/users', methods=['POST'])
@rate_limit(max_requests=10, window=60)  # Stricter limit for user creation
def create_user():
    try:
        data = request.json
        is_valid, result = validate_user_data(data)
        
        if not is_valid:
            return jsonify({"success": False, "message": result}), 400
        
        user = User(username=result['username'], email=result['email'])
        db.session.add(user)
        db.session.commit()
        return jsonify(user.to_dict()), 201
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Username or email already exists"}), 409
    except Exception as e:
        db.session.rollback()
        print(f"Error creating user: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@user_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())

@user_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.json
    user.username = data.get('username', user.username)
    user.email = data.get('email', user.email)
    db.session.commit()
    return jsonify(user.to_dict())

@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return '', 204

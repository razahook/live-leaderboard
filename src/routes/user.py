from flask import Blueprint, jsonify, request
from src.models.user import User, db

user_bp = Blueprint('user', __name__)

@user_bp.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([user.to_dict() for user in users])

@user_bp.route('/users', methods=['POST'])
def create_user():
    try:
        # INPUT VALIDATION FIX: Validate request data
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Validate required fields
        if 'username' not in data or not data['username']:
            return jsonify({"error": "Username is required"}), 400
        if 'email' not in data or not data['email']:
            return jsonify({"error": "Email is required"}), 400
        
        # Basic email validation
        if '@' not in data['email'] or '.' not in data['email']:
            return jsonify({"error": "Invalid email format"}), 400
        
        # Validate username length and characters
        username = data['username'].strip()
        if len(username) < 3 or len(username) > 80:
            return jsonify({"error": "Username must be between 3 and 80 characters"}), 400
        
        user = User(username=username, email=data['email'].strip())
        db.session.add(user)
        db.session.commit()
        return jsonify(user.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        # Handle unique constraint violations
        if "UNIQUE constraint failed" in str(e) or "duplicate key" in str(e):
            return jsonify({"error": "Username or email already exists"}), 409
        return jsonify({"error": str(e)}), 500

@user_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())

@user_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Validate username if provided
        if 'username' in data and data['username']:
            username = data['username'].strip()
            if len(username) < 3 or len(username) > 80:
                return jsonify({"error": "Username must be between 3 and 80 characters"}), 400
            user.username = username
        
        # Validate email if provided
        if 'email' in data and data['email']:
            email = data['email'].strip()
            if '@' not in email or '.' not in email:
                return jsonify({"error": "Invalid email format"}), 400
            user.email = email
        
        db.session.commit()
        return jsonify(user.to_dict())
    except Exception as e:
        db.session.rollback()
        if "UNIQUE constraint failed" in str(e) or "duplicate key" in str(e):
            return jsonify({"error": "Username or email already exists"}), 409
        return jsonify({"error": str(e)}), 500

@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return '', 204

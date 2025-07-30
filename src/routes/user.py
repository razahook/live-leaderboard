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
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        
        # Input validation
        if not username or len(username) < 3 or len(username) > 80:
            return jsonify({"error": "Username must be between 3 and 80 characters"}), 400
        
        if not email or '@' not in email or len(email) > 120:
            return jsonify({"error": "Valid email address required (max 120 characters)"}), 400
        
        # Check if user already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({"error": "Username already exists"}), 409
        
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            return jsonify({"error": "Email already exists"}), 409
        
        user = User(username=username, email=email)
        db.session.add(user)
        db.session.commit()
        return jsonify(user.to_dict()), 201
    except Exception as e:
        db.session.rollback()
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
            return jsonify({"error": "No data provided"}), 400
        
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        
        # Input validation
        if username and (len(username) < 3 or len(username) > 80):
            return jsonify({"error": "Username must be between 3 and 80 characters"}), 400
        
        if email and ('@' not in email or len(email) > 120):
            return jsonify({"error": "Valid email address required (max 120 characters)"}), 400
        
        # Check for conflicts if updating
        if username and username != user.username:
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                return jsonify({"error": "Username already exists"}), 409
        
        if email and email != user.email:
            existing_email = User.query.filter_by(email=email).first()
            if existing_email:
                return jsonify({"error": "Email already exists"}), 409
        
        # Update fields
        if username:
            user.username = username
        if email:
            user.email = email
        
        db.session.commit()
        return jsonify(user.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return '', 204

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_app(app):
    """Initialize the database with the Flask app"""
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///leaderboard.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    
    with app.app_context():
        # Create tables if they don't exist
        try:
            db.create_all()
        except Exception as e:
            print(f"Database initialization error (this is normal in a sandboxed environment): {e}")
            # In production, you'd want proper database setup
            pass
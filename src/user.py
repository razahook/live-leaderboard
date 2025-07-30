import os
from flask import Flask
from src.models.user import db

def init_app(app):
    """Initialize the database with the Flask app"""
    postgres_url = os.environ.get('POSTGRES_URL')
    if postgres_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = postgres_url.replace("postgres://", "postgresql://")
    else:
        db_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'app.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
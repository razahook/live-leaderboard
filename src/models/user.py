from flask_sqlalchemy import SQLAlchemy
import json
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    
    # Relationship to preferences
    preferences = db.relationship('UserPreferences', backref='user', uselist=False, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username}>'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'preferences': self.preferences.to_dict() if self.preferences else None
        }


class UserPreferences(db.Model):
    __tablename__ = 'user_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    
    # Theme settings
    theme = db.Column(db.String(20), default='light')  # 'light', 'dark', 'auto'
    
    # Auto-refresh settings
    auto_refresh_enabled = db.Column(db.Boolean, default=True)
    auto_refresh_interval = db.Column(db.Integer, default=30)  # seconds
    
    # Favorite streamers (stored as JSON)
    favorite_streamers = db.Column(db.Text, default='[]')
    
    # Stream quality preferences
    preferred_stream_quality = db.Column(db.String(20), default='source')  # 'source', '1080p', '720p', '480p'
    auto_quality = db.Column(db.Boolean, default=True)
    
    # Notification settings
    notifications_enabled = db.Column(db.Boolean, default=True)
    notify_favorite_streamers = db.Column(db.Boolean, default=True)
    notify_leaderboard_changes = db.Column(db.Boolean, default=False)
    notify_new_clips = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserPreferences user_id={self.user_id}>'
    
    def get_favorite_streamers(self):
        """Parse JSON string to list"""
        try:
            return json.loads(self.favorite_streamers) if self.favorite_streamers else []
        except (json.JSONDecodeError, TypeError):
            return []
    
    def set_favorite_streamers(self, streamers):
        """Convert list to JSON string"""
        if isinstance(streamers, list):
            self.favorite_streamers = json.dumps(streamers)
        else:
            self.favorite_streamers = '[]'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'theme': self.theme,
            'auto_refresh_enabled': self.auto_refresh_enabled,
            'auto_refresh_interval': self.auto_refresh_interval,
            'favorite_streamers': self.get_favorite_streamers(),
            'preferred_stream_quality': self.preferred_stream_quality,
            'auto_quality': self.auto_quality,
            'notifications_enabled': self.notifications_enabled,
            'notify_favorite_streamers': self.notify_favorite_streamers,
            'notify_leaderboard_changes': self.notify_leaderboard_changes,
            'notify_new_clips': self.notify_new_clips,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def create_default_preferences(cls, user_id):
        """Create default preferences for a user"""
        return cls(
            user_id=user_id,
            theme='light',
            auto_refresh_enabled=True,
            auto_refresh_interval=30,
            favorite_streamers='[]',
            preferred_stream_quality='source',
            auto_quality=True,
            notifications_enabled=True,
            notify_favorite_streamers=True,
            notify_leaderboard_changes=False,
            notify_new_clips=True
        )

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from models.user import db

class Clip(db.Model):
    """Model for storing clip metadata"""
    __tablename__ = 'clips'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Clip identification
    external_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    source = db.Column(db.String(50), nullable=False, default='twitch')  # twitch, local, etc.
    
    # Clip URLs
    url = db.Column(db.String(500), nullable=False)
    embed_url = db.Column(db.String(500))
    edit_url = db.Column(db.String(500))
    
    # Streamer information
    broadcaster_login = db.Column(db.String(100), nullable=False, index=True)
    streamer_id = db.Column(db.Integer, db.ForeignKey('streamers.id'), nullable=True)
    
    # Creator attribution
    creator_login = db.Column(db.String(100), nullable=True)
    created_by_user_id = db.Column(db.String(100), nullable=True)
    
    # Clip metadata
    title = db.Column(db.String(200))
    duration = db.Column(db.Integer)  # in seconds
    view_count = db.Column(db.Integer, default=0)
    thumbnail_url = db.Column(db.String(500))
    
    # Extra data (JSON)
    extra = db.Column(db.Text, default='{}')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Clip {self.external_id} by {self.broadcaster_login}>'
    
    def get_extra(self):
        """Parse extra JSON data"""
        try:
            import json
            return json.loads(self.extra) if self.extra else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_extra(self, data):
        """Set extra JSON data"""
        try:
            import json
            self.extra = json.dumps(data)
        except (TypeError, ValueError):
            self.extra = '{}'

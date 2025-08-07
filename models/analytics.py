from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
from sqlalchemy import func
from .user import db

class AnalyticsEvent(db.Model):
    """Model for tracking analytics events"""
    __tablename__ = 'analytics_events'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Event details
    event_type = db.Column(db.String(50), nullable=False, index=True)  # 'page_view', 'feature_use', 'api_call', etc.
    event_category = db.Column(db.String(50), nullable=False, index=True)  # 'leaderboard', 'twitch', 'user', etc.
    event_action = db.Column(db.String(100), nullable=False)  # 'view_leaderboard', 'watch_clip', 'update_preferences'
    event_label = db.Column(db.String(200))  # Optional additional label
    
    # User and session tracking
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    session_id = db.Column(db.String(100), index=True)  # Track anonymous sessions
    ip_address = db.Column(db.String(45))  # Support IPv6
    user_agent = db.Column(db.Text)
    
    # Additional data (stored as JSON)
    event_metadata = db.Column(db.Text, default='{}')  # Additional event data
    
    # Performance metrics
    response_time_ms = db.Column(db.Float)  # Response time for API calls
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<AnalyticsEvent {self.event_type}:{self.event_action}>'
    
    def get_metadata(self):
        """Parse JSON metadata"""
        try:
            return json.loads(self.event_metadata) if self.event_metadata else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_metadata(self, data):
        """Set metadata as JSON"""
        if isinstance(data, dict):
            self.event_metadata = json.dumps(data)
        else:
            self.event_metadata = '{}'
    
    def to_dict(self):
        return {
            'id': self.id,
            'event_type': self.event_type,
            'event_category': self.event_category,
            'event_action': self.event_action,
            'event_label': self.event_label,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'metadata': self.get_metadata(),
            'response_time_ms': self.response_time_ms,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def create_event(cls, event_type, event_category, event_action, 
                    event_label=None, user_id=None, session_id=None, 
                    ip_address=None, user_agent=None, metadata=None, 
                    response_time_ms=None):
        """Create a new analytics event"""
        event = cls(
            event_type=event_type,
            event_category=event_category,
            event_action=event_action,
            event_label=event_label,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            response_time_ms=response_time_ms
        )
        
        if metadata:
            event.set_metadata(metadata)
        
        return event

class AnalyticsSummary(db.Model):
    """Model for storing pre-computed analytics summaries"""
    __tablename__ = 'analytics_summaries'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Summary details
    summary_type = db.Column(db.String(50), nullable=False, index=True)  # 'daily', 'weekly', 'monthly'
    summary_date = db.Column(db.Date, nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False, index=True)
    
    # Metrics
    total_events = db.Column(db.Integer, default=0)
    unique_users = db.Column(db.Integer, default=0)
    unique_sessions = db.Column(db.Integer, default=0)
    
    # Performance metrics
    avg_response_time_ms = db.Column(db.Float)
    
    # Popular items (stored as JSON)
    popular_actions = db.Column(db.Text, default='{}')  # Top actions with counts
    popular_streamers = db.Column(db.Text, default='{}')  # Most viewed streamers
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<AnalyticsSummary {self.summary_type} {self.summary_date} {self.category}>'
    
    def get_popular_actions(self):
        """Parse popular actions JSON"""
        try:
            return json.loads(self.popular_actions) if self.popular_actions else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_popular_actions(self, data):
        """Set popular actions as JSON"""
        if isinstance(data, dict):
            self.popular_actions = json.dumps(data)
        else:
            self.popular_actions = '{}'
    
    def get_popular_streamers(self):
        """Parse popular streamers JSON"""
        try:
            return json.loads(self.popular_streamers) if self.popular_streamers else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_popular_streamers(self, data):
        """Set popular streamers as JSON"""
        if isinstance(data, dict):
            self.popular_streamers = json.dumps(data)
        else:
            self.popular_streamers = '{}'
    
    def to_dict(self):
        return {
            'id': self.id,
            'summary_type': self.summary_type,
            'summary_date': self.summary_date.isoformat() if self.summary_date else None,
            'category': self.category,
            'total_events': self.total_events,
            'unique_users': self.unique_users,
            'unique_sessions': self.unique_sessions,
            'avg_response_time_ms': self.avg_response_time_ms,
            'popular_actions': self.get_popular_actions(),
            'popular_streamers': self.get_popular_streamers(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class StreamerPopularity(db.Model):
    """Model for tracking streamer popularity metrics"""
    __tablename__ = 'streamer_popularity'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Streamer details
    streamer_username = db.Column(db.String(100), nullable=False, index=True)
    display_name = db.Column(db.String(100))
    
    # Popularity metrics
    view_count = db.Column(db.Integer, default=0)
    clip_view_count = db.Column(db.Integer, default=0)
    vod_view_count = db.Column(db.Integer, default=0)
    favorite_count = db.Column(db.Integer, default=0)  # How many users have this streamer as favorite
    
    # Time-based metrics
    total_view_time_seconds = db.Column(db.Integer, default=0)
    last_viewed_at = db.Column(db.DateTime)
    
    # Rankings
    current_rank = db.Column(db.Integer)
    peak_rank = db.Column(db.Integer)
    rank_change = db.Column(db.Integer, default=0)  # Change from previous period
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<StreamerPopularity {self.streamer_username}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'streamer_username': self.streamer_username,
            'display_name': self.display_name,
            'view_count': self.view_count,
            'clip_view_count': self.clip_view_count,
            'vod_view_count': self.vod_view_count,
            'favorite_count': self.favorite_count,
            'total_view_time_seconds': self.total_view_time_seconds,
            'last_viewed_at': self.last_viewed_at.isoformat() if self.last_viewed_at else None,
            'current_rank': self.current_rank,
            'peak_rank': self.peak_rank,
            'rank_change': self.rank_change,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def get_or_create(cls, streamer_username, display_name=None):
        """Get existing streamer popularity record or create new one"""
        streamer = cls.query.filter_by(streamer_username=streamer_username.lower()).first()
        if not streamer:
            streamer = cls(
                streamer_username=streamer_username.lower(),
                display_name=display_name or streamer_username
            )
            db.session.add(streamer)
        elif display_name and not streamer.display_name:
            streamer.display_name = display_name
        
        return streamer
    
    @classmethod
    def update_rankings(cls):
        """Update rankings for all streamers based on view counts"""
        streamers = cls.query.order_by(
            cls.view_count.desc(),
            cls.favorite_count.desc(),
            cls.clip_view_count.desc()
        ).all()
        
        for rank, streamer in enumerate(streamers, 1):
            old_rank = streamer.current_rank
            streamer.current_rank = rank
            
            if old_rank:
                streamer.rank_change = old_rank - rank  # Positive = moved up
            
            if not streamer.peak_rank or rank < streamer.peak_rank:
                streamer.peak_rank = rank
        
        db.session.commit()
        return len(streamers)
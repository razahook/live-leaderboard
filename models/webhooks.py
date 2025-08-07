from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import hmac
import hashlib
from .user import db

class WebhookEndpoint(db.Model):
    """Model for storing webhook endpoint configurations"""
    __tablename__ = 'webhook_endpoints'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Endpoint details
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    secret = db.Column(db.String(100))  # Secret for signature validation
    
    # Configuration
    is_active = db.Column(db.Boolean, default=True)
    event_types = db.Column(db.Text, default='[]')  # JSON array of event types to listen for
    
    # Security and rate limiting
    max_retries = db.Column(db.Integer, default=3)
    timeout_seconds = db.Column(db.Integer, default=30)
    rate_limit_per_minute = db.Column(db.Integer, default=60)
    
    # Headers to include (stored as JSON)
    custom_headers = db.Column(db.Text, default='{}')
    
    # Statistics
    total_calls = db.Column(db.Integer, default=0)
    successful_calls = db.Column(db.Integer, default=0)
    failed_calls = db.Column(db.Integer, default=0)
    last_called_at = db.Column(db.DateTime)
    last_success_at = db.Column(db.DateTime)
    last_error = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<WebhookEndpoint {self.name}>'
    
    def get_event_types(self):
        """Parse event types JSON"""
        try:
            return json.loads(self.event_types) if self.event_types else []
        except (json.JSONDecodeError, TypeError):
            return []
    
    def set_event_types(self, event_types):
        """Set event types as JSON"""
        if isinstance(event_types, list):
            self.event_types = json.dumps(event_types)
        else:
            self.event_types = '[]'
    
    def get_custom_headers(self):
        """Parse custom headers JSON"""
        try:
            return json.loads(self.custom_headers) if self.custom_headers else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_custom_headers(self, headers):
        """Set custom headers as JSON"""
        if isinstance(headers, dict):
            self.custom_headers = json.dumps(headers)
        else:
            self.custom_headers = '{}'
    
    def should_receive_event(self, event_type):
        """Check if this endpoint should receive a specific event type"""
        if not self.is_active:
            return False
        
        event_types = self.get_event_types()
        return not event_types or event_type in event_types or '*' in event_types
    
    def generate_signature(self, payload):
        """Generate HMAC signature for payload"""
        if not self.secret:
            return None
        
        if isinstance(payload, dict):
            payload = json.dumps(payload, sort_keys=True)
        
        signature = hmac.new(
            self.secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return f'sha256={signature}'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'is_active': self.is_active,
            'event_types': self.get_event_types(),
            'max_retries': self.max_retries,
            'timeout_seconds': self.timeout_seconds,
            'rate_limit_per_minute': self.rate_limit_per_minute,
            'custom_headers': self.get_custom_headers(),
            'statistics': {
                'total_calls': self.total_calls,
                'successful_calls': self.successful_calls,
                'failed_calls': self.failed_calls,
                'success_rate': round((self.successful_calls / self.total_calls * 100), 2) if self.total_calls > 0 else 0,
                'last_called_at': self.last_called_at.isoformat() if self.last_called_at else None,
                'last_success_at': self.last_success_at.isoformat() if self.last_success_at else None,
                'last_error': self.last_error
            },
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class WebhookEvent(db.Model):
    """Model for storing webhook events and their delivery status"""
    __tablename__ = 'webhook_events'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Event details
    event_type = db.Column(db.String(100), nullable=False, index=True)
    event_data = db.Column(db.Text, nullable=False)  # JSON payload
    
    # Delivery tracking
    endpoint_id = db.Column(db.Integer, db.ForeignKey('webhook_endpoints.id'), nullable=False, index=True)
    delivery_status = db.Column(db.String(20), default='pending', index=True)  # pending, delivered, failed, cancelled
    
    # Delivery attempts
    attempt_count = db.Column(db.Integer, default=0)
    max_attempts = db.Column(db.Integer, default=3)
    next_attempt_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Response details
    response_status_code = db.Column(db.Integer)
    response_body = db.Column(db.Text)
    response_headers = db.Column(db.Text)  # JSON
    delivery_duration_ms = db.Column(db.Float)
    
    # Error tracking
    error_message = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    delivered_at = db.Column(db.DateTime)
    failed_at = db.Column(db.DateTime)
    
    # Relationship
    endpoint = db.relationship('WebhookEndpoint', backref='events')
    
    def __repr__(self):
        return f'<WebhookEvent {self.event_type} -> {self.endpoint.name if self.endpoint else "Unknown"}>'
    
    def get_event_data(self):
        """Parse event data JSON"""
        try:
            return json.loads(self.event_data) if self.event_data else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_event_data(self, data):
        """Set event data as JSON"""
        if isinstance(data, dict):
            self.event_data = json.dumps(data)
        else:
            self.event_data = '{}'
    
    def get_response_headers(self):
        """Parse response headers JSON"""
        try:
            return json.loads(self.response_headers) if self.response_headers else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_response_headers(self, headers):
        """Set response headers as JSON"""
        if isinstance(headers, dict):
            self.response_headers = json.dumps(headers)
        else:
            self.response_headers = '{}'
    
    def mark_as_delivered(self, status_code, response_body=None, response_headers=None, duration_ms=None):
        """Mark event as successfully delivered"""
        self.delivery_status = 'delivered'
        self.response_status_code = status_code
        self.response_body = response_body[:1000] if response_body else None  # Limit response body size
        self.delivered_at = datetime.utcnow()
        
        if response_headers:
            self.set_response_headers(response_headers)
        
        if duration_ms:
            self.delivery_duration_ms = duration_ms
        
        # Update endpoint statistics
        if self.endpoint:
            self.endpoint.successful_calls += 1
            self.endpoint.last_success_at = self.delivered_at
    
    def mark_as_failed(self, error_message, status_code=None, response_body=None, duration_ms=None):
        """Mark event as failed"""
        self.delivery_status = 'failed'
        self.error_message = error_message[:500] if error_message else None  # Limit error message size
        self.failed_at = datetime.utcnow()
        
        if status_code:
            self.response_status_code = status_code
        
        if response_body:
            self.response_body = response_body[:1000]
        
        if duration_ms:
            self.delivery_duration_ms = duration_ms
        
        # Update endpoint statistics
        if self.endpoint:
            self.endpoint.failed_calls += 1
            self.endpoint.last_error = error_message
    
    def should_retry(self):
        """Check if this event should be retried"""
        return (
            self.delivery_status in ['pending', 'failed'] and
            self.attempt_count < self.max_attempts and
            datetime.utcnow() >= self.next_attempt_at
        )
    
    def calculate_next_attempt(self):
        """Calculate when the next delivery attempt should be made (exponential backoff)"""
        base_delay = 60  # 1 minute base delay
        delay_seconds = base_delay * (2 ** self.attempt_count)  # Exponential backoff
        max_delay = 3600  # Max 1 hour delay
        
        delay_seconds = min(delay_seconds, max_delay)
        self.next_attempt_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
    
    def to_dict(self):
        return {
            'id': self.id,
            'event_type': self.event_type,
            'event_data': self.get_event_data(),
            'endpoint': {
                'id': self.endpoint.id,
                'name': self.endpoint.name,
                'url': self.endpoint.url
            } if self.endpoint else None,
            'delivery_status': self.delivery_status,
            'attempt_count': self.attempt_count,
            'max_attempts': self.max_attempts,
            'next_attempt_at': self.next_attempt_at.isoformat() if self.next_attempt_at else None,
            'response': {
                'status_code': self.response_status_code,
                'body': self.response_body,
                'headers': self.get_response_headers(),
                'duration_ms': self.delivery_duration_ms
            },
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'failed_at': self.failed_at.isoformat() if self.failed_at else None
        }
    
    @classmethod
    def create_for_all_endpoints(cls, event_type, event_data):
        """Create webhook events for all endpoints that should receive this event type"""
        endpoints = WebhookEndpoint.query.filter(WebhookEndpoint.is_active == True).all()
        created_events = []
        
        for endpoint in endpoints:
            if endpoint.should_receive_event(event_type):
                event = cls(
                    event_type=event_type,
                    endpoint_id=endpoint.id,
                    max_attempts=endpoint.max_retries
                )
                event.set_event_data(event_data)
                
                db.session.add(event)
                created_events.append(event)
                
                # Update endpoint statistics
                endpoint.total_calls += 1
                endpoint.last_called_at = datetime.utcnow()
        
        return created_events
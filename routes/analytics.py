from flask import Blueprint, request, jsonify, session
from models.user import db
from models.analytics import AnalyticsEvent, AnalyticsSummary, StreamerPopularity
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, text
import uuid
import logging
from functools import wraps
import time

analytics_bp = Blueprint('analytics', __name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_session_id():
    """Get or create session ID for anonymous tracking"""
    if 'analytics_session_id' not in session:
        session['analytics_session_id'] = str(uuid.uuid4())
    return session['analytics_session_id']

def get_client_ip():
    """Get client IP address"""
    return request.environ.get('HTTP_X_REAL_IP', request.remote_addr)

def track_analytics(event_type, event_category, event_action, event_label=None, metadata=None):
    """Helper function to track analytics events"""
    try:
        # Get user ID if authenticated (you'll need to implement this based on your auth system)
        user_id = session.get('user_id')  # Adjust based on your auth implementation
        
        event = AnalyticsEvent.create_event(
            event_type=event_type,
            event_category=event_category,
            event_action=event_action,
            event_label=event_label,
            user_id=user_id,
            session_id=get_session_id(),
            ip_address=get_client_ip(),
            user_agent=request.headers.get('User-Agent'),
            metadata=metadata
        )
        
        db.session.add(event)
        db.session.commit()
        
        logger.debug(f"Analytics event tracked: {event_type}:{event_action}")
        
    except Exception as e:
        logger.error(f"Failed to track analytics event: {str(e)}")
        db.session.rollback()

def analytics_decorator(event_category, event_action, event_label=None):
    """Decorator to automatically track API endpoint usage"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = f(*args, **kwargs)
                
                # Calculate response time
                response_time_ms = round((time.time() - start_time) * 1000, 2)
                
                # Track successful API call
                metadata = {
                    'endpoint': request.endpoint,
                    'method': request.method,
                    'status': 'success'
                }
                
                # Get status code from response if it's a tuple
                status_code = 200
                if isinstance(result, tuple) and len(result) > 1:
                    status_code = result[1]
                    metadata['status_code'] = status_code
                
                event = AnalyticsEvent.create_event(
                    event_type='api_call',
                    event_category=event_category,
                    event_action=event_action,
                    event_label=event_label,
                    user_id=session.get('user_id'),
                    session_id=get_session_id(),
                    ip_address=get_client_ip(),
                    user_agent=request.headers.get('User-Agent'),
                    metadata=metadata,
                    response_time_ms=response_time_ms
                )
                
                db.session.add(event)
                db.session.commit()
                
                return result
                
            except Exception as e:
                response_time_ms = round((time.time() - start_time) * 1000, 2)
                
                # Track failed API call
                metadata = {
                    'endpoint': request.endpoint,
                    'method': request.method,
                    'status': 'error',
                    'error': str(e)
                }
                
                event = AnalyticsEvent.create_event(
                    event_type='api_call',
                    event_category=event_category,
                    event_action=f"{event_action}_error",
                    event_label=event_label,
                    user_id=session.get('user_id'),
                    session_id=get_session_id(),
                    ip_address=get_client_ip(),
                    user_agent=request.headers.get('User-Agent'),
                    metadata=metadata,
                    response_time_ms=response_time_ms
                )
                
                db.session.add(event)
                db.session.commit()
                
                raise e
        
        return decorated_function
    return decorator

@analytics_bp.route('/analytics/track', methods=['POST'])
def track_event():
    """Endpoint for frontend to track custom events"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['event_type', 'event_category', 'event_action']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
        
        # Track the event
        track_analytics(
            event_type=data['event_type'],
            event_category=data['event_category'],
            event_action=data['event_action'],
            event_label=data.get('event_label'),
            metadata=data.get('metadata')
        )
        
        return jsonify({'success': True, 'message': 'Event tracked successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error tracking custom event: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to track event'}), 500

@analytics_bp.route('/analytics/streamer/<streamer_username>/view', methods=['POST'])
def track_streamer_view(streamer_username):
    """Track when a user views a streamer"""
    try:
        data = request.get_json() or {}
        view_duration = data.get('view_duration_seconds', 0)
        view_type = data.get('view_type', 'profile')  # 'profile', 'clip', 'vod', 'live'
        
        # Track analytics event
        track_analytics(
            event_type='streamer_interaction',
            event_category='streamer',
            event_action=f'view_{view_type}',
            event_label=streamer_username,
            metadata={
                'streamer_username': streamer_username,
                'view_duration_seconds': view_duration,
                'view_type': view_type
            }
        )
        
        # Update streamer popularity
        streamer = StreamerPopularity.get_or_create(streamer_username)
        
        if view_type == 'clip':
            streamer.clip_view_count += 1
        elif view_type == 'vod':
            streamer.vod_view_count += 1
        else:
            streamer.view_count += 1
        
        if view_duration > 0:
            streamer.total_view_time_seconds += view_duration
        
        streamer.last_viewed_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Streamer view tracked'}), 200
        
    except Exception as e:
        logger.error(f"Error tracking streamer view: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to track streamer view'}), 500

@analytics_bp.route('/analytics/summary', methods=['GET'])
def get_analytics_summary():
    """Get analytics summary data"""
    try:
        # Get query parameters
        days = request.args.get('days', 7, type=int)
        category = request.args.get('category')
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Base query
        query = AnalyticsEvent.query.filter(
            AnalyticsEvent.created_at >= start_date,
            AnalyticsEvent.created_at <= end_date
        )
        
        if category:
            query = query.filter(AnalyticsEvent.event_category == category)
        
        # Get total events
        total_events = query.count()
        
        # Get unique users and sessions
        unique_users = query.filter(AnalyticsEvent.user_id.isnot(None)).distinct(AnalyticsEvent.user_id).count()
        unique_sessions = query.distinct(AnalyticsEvent.session_id).count()
        
        # Get popular actions
        popular_actions = db.session.query(
            AnalyticsEvent.event_action,
            func.count(AnalyticsEvent.id).label('count')
        ).filter(
            AnalyticsEvent.created_at >= start_date,
            AnalyticsEvent.created_at <= end_date
        )
        
        if category:
            popular_actions = popular_actions.filter(AnalyticsEvent.event_category == category)
        
        popular_actions = popular_actions.group_by(AnalyticsEvent.event_action).order_by(desc('count')).limit(10).all()
        
        # Get events by day
        events_by_day = db.session.query(
            func.date(AnalyticsEvent.created_at).label('date'),
            func.count(AnalyticsEvent.id).label('count')
        ).filter(
            AnalyticsEvent.created_at >= start_date,
            AnalyticsEvent.created_at <= end_date
        )
        
        if category:
            events_by_day = events_by_day.filter(AnalyticsEvent.event_category == category)
        
        events_by_day = events_by_day.group_by(func.date(AnalyticsEvent.created_at)).order_by('date').all()
        
        # Get average response time for API calls
        avg_response_time = db.session.query(
            func.avg(AnalyticsEvent.response_time_ms)
        ).filter(
            AnalyticsEvent.created_at >= start_date,
            AnalyticsEvent.created_at <= end_date,
            AnalyticsEvent.event_type == 'api_call',
            AnalyticsEvent.response_time_ms.isnot(None)
        ).scalar()
        
        return jsonify({
            'success': True,
            'data': {
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                },
                'summary': {
                    'total_events': total_events,
                    'unique_users': unique_users,
                    'unique_sessions': unique_sessions,
                    'avg_response_time_ms': round(avg_response_time, 2) if avg_response_time else None
                },
                'popular_actions': [
                    {'action': action, 'count': count} 
                    for action, count in popular_actions
                ],
                'events_by_day': [
                    {'date': str(date), 'count': count} 
                    for date, count in events_by_day
                ]
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting analytics summary: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get analytics summary'}), 500

@analytics_bp.route('/analytics/streamers/popular', methods=['GET'])
def get_popular_streamers():
    """Get popular streamers based on analytics"""
    try:
        limit = request.args.get('limit', 20, type=int)
        days = request.args.get('days', 7, type=int)
        
        # Get popular streamers from database
        streamers = StreamerPopularity.query.order_by(
            desc(StreamerPopularity.view_count),
            desc(StreamerPopularity.favorite_count),
            desc(StreamerPopularity.clip_view_count)
        ).limit(limit).all()
        
        # Also get recent activity from analytics events
        recent_date = datetime.utcnow() - timedelta(days=days)
        recent_activity = db.session.query(
            AnalyticsEvent.event_label.label('streamer'),
            func.count(AnalyticsEvent.id).label('recent_views')
        ).filter(
            AnalyticsEvent.event_category == 'streamer',
            AnalyticsEvent.event_action.like('view_%'),
            AnalyticsEvent.event_label.isnot(None),
            AnalyticsEvent.created_at >= recent_date
        ).group_by(AnalyticsEvent.event_label).order_by(desc('recent_views')).limit(limit).all()
        
        return jsonify({
            'success': True,
            'data': {
                'popular_streamers': [streamer.to_dict() for streamer in streamers],
                'recent_activity': [
                    {'streamer': streamer, 'recent_views': views}
                    for streamer, views in recent_activity
                ]
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting popular streamers: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get popular streamers'}), 500

@analytics_bp.route('/analytics/performance', methods=['GET'])
def get_performance_metrics():
    """Get API performance metrics"""
    try:
        days = request.args.get('days', 7, type=int)
        endpoint = request.args.get('endpoint')
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Base query for API calls
        query = AnalyticsEvent.query.filter(
            AnalyticsEvent.event_type == 'api_call',
            AnalyticsEvent.created_at >= start_date,
            AnalyticsEvent.created_at <= end_date,
            AnalyticsEvent.response_time_ms.isnot(None)
        )
        
        if endpoint:
            # Filter by endpoint if specified
            query = query.filter(AnalyticsEvent.event_metadata.contains(f'"endpoint": "{endpoint}"'))
        
        # Get performance statistics
        performance_stats = db.session.query(
            func.avg(AnalyticsEvent.response_time_ms).label('avg_response_time'),
            func.min(AnalyticsEvent.response_time_ms).label('min_response_time'),
            func.max(AnalyticsEvent.response_time_ms).label('max_response_time'),
            func.count(AnalyticsEvent.id).label('total_calls')
        ).filter(
            AnalyticsEvent.event_type == 'api_call',
            AnalyticsEvent.created_at >= start_date,
            AnalyticsEvent.created_at <= end_date,
            AnalyticsEvent.response_time_ms.isnot(None)
        )
        
        if endpoint:
            performance_stats = performance_stats.filter(
                AnalyticsEvent.event_metadata.contains(f'"endpoint": "{endpoint}"')
            )
        
        stats = performance_stats.first()
        
        # Get slowest endpoints
        slowest_endpoints = db.session.query(
            func.json_extract(AnalyticsEvent.event_metadata, '$.endpoint').label('endpoint'),
            func.avg(AnalyticsEvent.response_time_ms).label('avg_response_time'),
            func.count(AnalyticsEvent.id).label('call_count')
        ).filter(
            AnalyticsEvent.event_type == 'api_call',
            AnalyticsEvent.created_at >= start_date,
            AnalyticsEvent.created_at <= end_date,
            AnalyticsEvent.response_time_ms.isnot(None)
        ).group_by(
            func.json_extract(AnalyticsEvent.event_metadata, '$.endpoint')
        ).order_by(desc('avg_response_time')).limit(10).all()
        
        return jsonify({
            'success': True,
            'data': {
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                },
                'performance': {
                    'avg_response_time_ms': round(stats.avg_response_time, 2) if stats.avg_response_time else None,
                    'min_response_time_ms': stats.min_response_time,
                    'max_response_time_ms': stats.max_response_time,
                    'total_api_calls': stats.total_calls
                },
                'slowest_endpoints': [
                    {
                        'endpoint': endpoint,
                        'avg_response_time_ms': round(avg_time, 2),
                        'call_count': count
                    }
                    for endpoint, avg_time, count in slowest_endpoints
                ]
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get performance metrics'}), 500

@analytics_bp.route('/analytics/cleanup', methods=['POST'])
def cleanup_old_events():
    """Clean up old analytics events"""
    try:
        # Get days parameter (default: keep events for 90 days)
        days_to_keep = request.json.get('days_to_keep', 90) if request.json else 90
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Delete old events
        deleted_count = AnalyticsEvent.query.filter(
            AnalyticsEvent.created_at < cutoff_date
        ).delete()
        
        db.session.commit()
        
        logger.info(f"Cleaned up {deleted_count} old analytics events")
        
        return jsonify({
            'success': True,
            'message': f'Cleaned up {deleted_count} events older than {days_to_keep} days'
        }), 200
        
    except Exception as e:
        logger.error(f"Error cleaning up analytics events: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to cleanup analytics events'}), 500

# Middleware function to track page views (can be used in main app)
def track_page_view():
    """Track page view - call this from your main routes"""
    try:
        track_analytics(
            event_type='page_view',
            event_category='frontend',
            event_action='page_view',
            event_label=request.endpoint,
            metadata={
                'url': request.url,
                'referrer': request.referrer
            }
        )
    except Exception as e:
        logger.error(f"Failed to track page view: {str(e)}")

# Export the decorator for use in other routes
__all__ = ['analytics_bp', 'analytics_decorator', 'track_analytics', 'track_page_view']
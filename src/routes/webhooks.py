from flask import Blueprint, request, jsonify
from models.user import db
from models.webhooks import WebhookEndpoint, WebhookEvent
from datetime import datetime, timedelta
from sqlalchemy import func, desc
import requests
import json
import time
import logging
from threading import Thread
import queue
import hmac
import hashlib
from functools import wraps

webhooks_bp = Blueprint('webhooks', __name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Webhook delivery queue (in production, use Redis or similar)
webhook_queue = queue.Queue()

def validate_webhook_secret(f):
    """Decorator to validate webhook secret for admin endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Simple validation - in production, use proper authentication
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
        # You can implement proper API key validation here
        return f(*args, **kwargs)
    return decorated_function

@webhooks_bp.route('/webhooks/endpoints', methods=['GET'])
@validate_webhook_secret
def list_webhook_endpoints():
    """Get all webhook endpoints"""
    try:
        endpoints = WebhookEndpoint.query.all()
        
        return jsonify({
            'success': True,
            'data': [endpoint.to_dict() for endpoint in endpoints]
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing webhook endpoints: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to list endpoints'}), 500

@webhooks_bp.route('/webhooks/endpoints', methods=['POST'])
@validate_webhook_secret
def create_webhook_endpoint():
    """Create a new webhook endpoint"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['name', 'url']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
        
        # Create new endpoint
        endpoint = WebhookEndpoint(
            name=data['name'],
            url=data['url'],
            secret=data.get('secret'),
            is_active=data.get('is_active', True),
            max_retries=data.get('max_retries', 3),
            timeout_seconds=data.get('timeout_seconds', 30),
            rate_limit_per_minute=data.get('rate_limit_per_minute', 60)
        )
        
        # Set event types
        if 'event_types' in data:
            endpoint.set_event_types(data['event_types'])
        
        # Set custom headers
        if 'custom_headers' in data:
            endpoint.set_custom_headers(data['custom_headers'])
        
        db.session.add(endpoint)
        db.session.commit()
        
        logger.info(f"Created webhook endpoint: {endpoint.name}")
        
        return jsonify({
            'success': True,
            'data': endpoint.to_dict(),
            'message': 'Webhook endpoint created successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating webhook endpoint: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to create endpoint'}), 500

@webhooks_bp.route('/webhooks/endpoints/<int:endpoint_id>', methods=['PUT'])
@validate_webhook_secret
def update_webhook_endpoint(endpoint_id):
    """Update a webhook endpoint"""
    try:
        endpoint = WebhookEndpoint.query.get(endpoint_id)
        if not endpoint:
            return jsonify({'success': False, 'error': 'Endpoint not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Update fields
        if 'name' in data:
            endpoint.name = data['name']
        if 'url' in data:
            endpoint.url = data['url']
        if 'secret' in data:
            endpoint.secret = data['secret']
        if 'is_active' in data:
            endpoint.is_active = data['is_active']
        if 'max_retries' in data:
            endpoint.max_retries = data['max_retries']
        if 'timeout_seconds' in data:
            endpoint.timeout_seconds = data['timeout_seconds']
        if 'rate_limit_per_minute' in data:
            endpoint.rate_limit_per_minute = data['rate_limit_per_minute']
        
        # Update event types
        if 'event_types' in data:
            endpoint.set_event_types(data['event_types'])
        
        # Update custom headers
        if 'custom_headers' in data:
            endpoint.set_custom_headers(data['custom_headers'])
        
        db.session.commit()
        
        logger.info(f"Updated webhook endpoint: {endpoint.name}")
        
        return jsonify({
            'success': True,
            'data': endpoint.to_dict(),
            'message': 'Webhook endpoint updated successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating webhook endpoint: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to update endpoint'}), 500

@webhooks_bp.route('/webhooks/endpoints/<int:endpoint_id>', methods=['DELETE'])
@validate_webhook_secret
def delete_webhook_endpoint(endpoint_id):
    """Delete a webhook endpoint"""
    try:
        endpoint = WebhookEndpoint.query.get(endpoint_id)
        if not endpoint:
            return jsonify({'success': False, 'error': 'Endpoint not found'}), 404
        
        endpoint_name = endpoint.name
        
        # Delete associated events first
        WebhookEvent.query.filter_by(endpoint_id=endpoint_id).delete()
        
        # Delete endpoint
        db.session.delete(endpoint)
        db.session.commit()
        
        logger.info(f"Deleted webhook endpoint: {endpoint_name}")
        
        return jsonify({
            'success': True,
            'message': 'Webhook endpoint deleted successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting webhook endpoint: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to delete endpoint'}), 500

@webhooks_bp.route('/webhooks/endpoints/<int:endpoint_id>/test', methods=['POST'])
@validate_webhook_secret
def test_webhook_endpoint(endpoint_id):
    """Test a webhook endpoint with a sample payload"""
    try:
        endpoint = WebhookEndpoint.query.get(endpoint_id)
        if not endpoint:
            return jsonify({'success': False, 'error': 'Endpoint not found'}), 404
        
        # Create test payload
        test_payload = {
            'event_type': 'webhook.test',
            'timestamp': datetime.utcnow().isoformat(),
            'data': {
                'message': 'This is a test webhook event',
                'endpoint_id': endpoint_id,
                'endpoint_name': endpoint.name
            }
        }
        
        # Trigger webhook delivery
        success, response = deliver_webhook(endpoint, test_payload)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Test webhook delivered successfully',
                'response': response
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Test webhook delivery failed',
                'error': response
            }), 400
        
    except Exception as e:
        logger.error(f"Error testing webhook endpoint: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to test endpoint'}), 500

@webhooks_bp.route('/webhooks/events', methods=['GET'])
@validate_webhook_secret
def list_webhook_events():
    """Get webhook events with optional filtering"""
    try:
        # Query parameters
        endpoint_id = request.args.get('endpoint_id', type=int)
        event_type = request.args.get('event_type')
        status = request.args.get('status')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Build query
        query = WebhookEvent.query
        
        if endpoint_id:
            query = query.filter(WebhookEvent.endpoint_id == endpoint_id)
        
        if event_type:
            query = query.filter(WebhookEvent.event_type == event_type)
        
        if status:
            query = query.filter(WebhookEvent.delivery_status == status)
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination and ordering
        events = query.order_by(WebhookEvent.created_at.desc()).offset(offset).limit(limit).all()
        
        return jsonify({
            'success': True,
            'data': {
                'events': [event.to_dict() for event in events],
                'pagination': {
                    'total': total_count,
                    'limit': limit,
                    'offset': offset,
                    'has_more': offset + limit < total_count
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing webhook events: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to list events'}), 500

@webhooks_bp.route('/webhooks/events/<int:event_id>/retry', methods=['POST'])
@validate_webhook_secret
def retry_webhook_event(event_id):
    """Manually retry a failed webhook event"""
    try:
        event = WebhookEvent.query.get(event_id)
        if not event:
            return jsonify({'success': False, 'error': 'Event not found'}), 404
        
        if event.delivery_status == 'delivered':
            return jsonify({'success': False, 'error': 'Event already delivered'}), 400
        
        # Reset event for retry
        event.delivery_status = 'pending'
        event.next_attempt_at = datetime.utcnow()
        event.error_message = None
        
        db.session.commit()
        
        # Queue for immediate retry
        webhook_queue.put(event.id)
        
        return jsonify({
            'success': True,
            'message': 'Event queued for retry'
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrying webhook event: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to retry event'}), 500

@webhooks_bp.route('/webhooks/trigger', methods=['POST'])
def trigger_webhook():
    """Trigger a webhook event (can be called by internal systems)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Validate required fields
        if 'event_type' not in data:
            return jsonify({'success': False, 'error': 'Missing event_type'}), 400
        
        event_type = data['event_type']
        event_data = data.get('data', {})
        
        # Add metadata
        event_data.update({
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'api_trigger'
        })
        
        # Create events for all matching endpoints
        events = WebhookEvent.create_for_all_endpoints(event_type, event_data)
        
        if events:
            db.session.commit()
            
            # Queue events for delivery
            for event in events:
                webhook_queue.put(event.id)
            
            logger.info(f"Triggered {len(events)} webhook events for {event_type}")
            
            return jsonify({
                'success': True,
                'message': f'Triggered {len(events)} webhook events',
                'event_ids': [event.id for event in events]
            }), 200
        else:
            return jsonify({
                'success': True,
                'message': 'No active endpoints found for this event type',
                'event_ids': []
            }), 200
        
    except Exception as e:
        logger.error(f"Error triggering webhook: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to trigger webhook'}), 500

@webhooks_bp.route('/webhooks/stats', methods=['GET'])
@validate_webhook_secret
def get_webhook_stats():
    """Get webhook delivery statistics"""
    try:
        days = request.args.get('days', 7, type=int)
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Overall stats
        total_events = WebhookEvent.query.filter(WebhookEvent.created_at >= start_date).count()
        delivered_events = WebhookEvent.query.filter(
            WebhookEvent.created_at >= start_date,
            WebhookEvent.delivery_status == 'delivered'
        ).count()
        failed_events = WebhookEvent.query.filter(
            WebhookEvent.created_at >= start_date,
            WebhookEvent.delivery_status == 'failed'
        ).count()
        pending_events = WebhookEvent.query.filter(
            WebhookEvent.created_at >= start_date,
            WebhookEvent.delivery_status == 'pending'
        ).count()
        
        # Average delivery time
        avg_delivery_time = db.session.query(
            func.avg(WebhookEvent.delivery_duration_ms)
        ).filter(
            WebhookEvent.created_at >= start_date,
            WebhookEvent.delivery_status == 'delivered',
            WebhookEvent.delivery_duration_ms.isnot(None)
        ).scalar()
        
        # Stats by endpoint
        endpoint_stats = db.session.query(
            WebhookEndpoint.name,
            WebhookEndpoint.id,
            func.count(WebhookEvent.id).label('total_events'),
            func.sum(func.case([(WebhookEvent.delivery_status == 'delivered', 1)], else_=0)).label('delivered'),
            func.sum(func.case([(WebhookEvent.delivery_status == 'failed', 1)], else_=0)).label('failed')
        ).join(WebhookEvent).filter(
            WebhookEvent.created_at >= start_date
        ).group_by(WebhookEndpoint.id, WebhookEndpoint.name).all()
        
        # Stats by event type
        event_type_stats = db.session.query(
            WebhookEvent.event_type,
            func.count(WebhookEvent.id).label('total_events'),
            func.sum(func.case([(WebhookEvent.delivery_status == 'delivered', 1)], else_=0)).label('delivered'),
            func.sum(func.case([(WebhookEvent.delivery_status == 'failed', 1)], else_=0)).label('failed')
        ).filter(
            WebhookEvent.created_at >= start_date
        ).group_by(WebhookEvent.event_type).all()
        
        return jsonify({
            'success': True,
            'data': {
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': datetime.utcnow().isoformat(),
                    'days': days
                },
                'overall': {
                    'total_events': total_events,
                    'delivered_events': delivered_events,
                    'failed_events': failed_events,
                    'pending_events': pending_events,
                    'success_rate': round((delivered_events / total_events * 100), 2) if total_events > 0 else 0,
                    'avg_delivery_time_ms': round(avg_delivery_time, 2) if avg_delivery_time else None
                },
                'by_endpoint': [
                    {
                        'endpoint_name': name,
                        'endpoint_id': endpoint_id,
                        'total_events': total,
                        'delivered': delivered,
                        'failed': failed,
                        'success_rate': round((delivered / total * 100), 2) if total > 0 else 0
                    }
                    for name, endpoint_id, total, delivered, failed in endpoint_stats
                ],
                'by_event_type': [
                    {
                        'event_type': event_type,
                        'total_events': total,
                        'delivered': delivered,
                        'failed': failed,
                        'success_rate': round((delivered / total * 100), 2) if total > 0 else 0
                    }
                    for event_type, total, delivered, failed in event_type_stats
                ]
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting webhook stats: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get webhook stats'}), 500

def deliver_webhook(endpoint, payload):
    """Deliver a webhook to an endpoint"""
    try:
        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'ApexLeaderboard-Webhook/1.0'
        }
        
        # Add custom headers
        custom_headers = endpoint.get_custom_headers()
        headers.update(custom_headers)
        
        # Add signature if secret is provided
        if endpoint.secret:
            signature = endpoint.generate_signature(payload)
            if signature:
                headers['X-Webhook-Signature'] = signature
        
        # Make the request
        start_time = time.time()
        response = requests.post(
            endpoint.url,
            json=payload,
            headers=headers,
            timeout=endpoint.timeout_seconds
        )
        duration_ms = round((time.time() - start_time) * 1000, 2)
        
        # Check if successful
        if 200 <= response.status_code < 300:
            return True, {
                'status_code': response.status_code,
                'response_body': response.text[:500],  # Limit response body
                'duration_ms': duration_ms
            }
        else:
            return False, f"HTTP {response.status_code}: {response.text[:200]}"
    
    except requests.Timeout:
        return False, "Request timeout"
    except requests.ConnectionError:
        return False, "Connection error"
    except Exception as e:
        return False, str(e)

def webhook_delivery_worker():
    """Background worker to process webhook deliveries"""
    while True:
        try:
            # Get event from queue (blocking call)
            event_id = webhook_queue.get(timeout=30)
            
            if event_id is None:  # Shutdown signal
                break
            
            # Get event from database
            event = WebhookEvent.query.get(event_id)
            if not event or not event.should_retry():
                continue
            
            # Update attempt count
            event.attempt_count += 1
            event.next_attempt_at = datetime.utcnow()
            
            # Prepare payload
            payload = {
                'event_type': event.event_type,
                'timestamp': event.created_at.isoformat(),
                'data': event.get_event_data()
            }
            
            # Deliver webhook
            success, response = deliver_webhook(event.endpoint, payload)
            
            if success:
                event.mark_as_delivered(
                    status_code=response['status_code'],
                    response_body=response.get('response_body'),
                    duration_ms=response.get('duration_ms')
                )
                logger.info(f"Webhook delivered successfully: {event.id}")
            else:
                event.mark_as_failed(response)
                
                # Schedule retry if attempts remaining
                if event.attempt_count < event.max_attempts:
                    event.calculate_next_attempt()
                    logger.warning(f"Webhook delivery failed, will retry: {event.id}")
                else:
                    logger.error(f"Webhook delivery failed permanently: {event.id}")
            
            db.session.commit()
            
        except queue.Empty:
            # No events to process, continue
            continue
        except Exception as e:
            logger.error(f"Error in webhook delivery worker: {str(e)}")
            continue

# Start webhook delivery worker in background thread
delivery_thread = Thread(target=webhook_delivery_worker, daemon=True)
delivery_thread.start()

# Utility functions for triggering webhooks from other parts of the application
def trigger_leaderboard_update(leaderboard_data):
    """Trigger webhook for leaderboard updates"""
    trigger_webhook_event('leaderboard.updated', {
        'platform': leaderboard_data.get('platform'),
        'player_count': len(leaderboard_data.get('players', [])),
        'updated_at': datetime.utcnow().isoformat()
    })

def trigger_stream_status_change(streamer_username, is_live, stream_data=None):
    """Trigger webhook for stream status changes"""
    trigger_webhook_event('stream.status_changed', {
        'streamer_username': streamer_username,
        'is_live': is_live,
        'stream_data': stream_data or {},
        'changed_at': datetime.utcnow().isoformat()
    })

def trigger_user_preference_update(user_id, preferences_data):
    """Trigger webhook for user preference updates"""
    trigger_webhook_event('user.preferences_updated', {
        'user_id': user_id,
        'preferences': preferences_data,
        'updated_at': datetime.utcnow().isoformat()
    })

def trigger_webhook_event(event_type, event_data):
    """Utility function to trigger webhook events"""
    try:
        events = WebhookEvent.create_for_all_endpoints(event_type, event_data)
        
        if events:
            db.session.commit()
            
            # Queue events for delivery
            for event in events:
                webhook_queue.put(event.id)
            
            logger.debug(f"Queued {len(events)} webhook events for {event_type}")
    
    except Exception as e:
        logger.error(f"Error triggering webhook event {event_type}: {str(e)}")
        db.session.rollback()

# Export webhook trigger functions
__all__ = [
    'webhooks_bp', 
    'trigger_leaderboard_update', 
    'trigger_stream_status_change', 
    'trigger_user_preference_update',
    'trigger_webhook_event'
]

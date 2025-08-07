from flask import Blueprint, request, jsonify
from models.user import db, User, UserPreferences
from functools import wraps
import logging

user_preferences_bp = Blueprint('user_preferences', __name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_user_id(f):
    """Decorator to validate user_id parameter"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = kwargs.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'User ID is required'}), 400
        
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid user ID format'}), 400
        
        # Check if user exists
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        kwargs['user_id'] = user_id
        kwargs['user'] = user
        return f(*args, **kwargs)
    return decorated_function

@user_preferences_bp.route('/user/<int:user_id>/preferences', methods=['GET'])
@validate_user_id
def get_user_preferences(user_id, user):
    """Get user preferences"""
    try:
        preferences = UserPreferences.query.filter_by(user_id=user_id).first()
        
        if not preferences:
            # Create default preferences if none exist
            preferences = UserPreferences.create_default_preferences(user_id)
            db.session.add(preferences)
            db.session.commit()
            logger.info(f"Created default preferences for user {user_id}")
        
        return jsonify({
            'success': True,
            'data': preferences.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting preferences for user {user_id}: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve user preferences'
        }), 500

@user_preferences_bp.route('/user/<int:user_id>/preferences', methods=['POST', 'PUT'])
@validate_user_id
def update_user_preferences(user_id, user):
    """Create or update user preferences"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Get existing preferences or create new ones
        preferences = UserPreferences.query.filter_by(user_id=user_id).first()
        if not preferences:
            preferences = UserPreferences.create_default_preferences(user_id)
            db.session.add(preferences)
        
        # Validate and update preferences
        update_result = _update_preferences_from_data(preferences, data)
        if not update_result['success']:
            return jsonify(update_result), 400
        
        db.session.commit()
        logger.info(f"Updated preferences for user {user_id}")
        
        return jsonify({
            'success': True,
            'data': preferences.to_dict(),
            'message': 'Preferences updated successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating preferences for user {user_id}: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to update user preferences'
        }), 500

@user_preferences_bp.route('/user/<int:user_id>/preferences/reset', methods=['POST'])
@validate_user_id
def reset_user_preferences(user_id, user):
    """Reset user preferences to defaults"""
    try:
        preferences = UserPreferences.query.filter_by(user_id=user_id).first()
        
        if preferences:
            # Update existing preferences to defaults
            default_prefs = UserPreferences.create_default_preferences(user_id)
            _copy_preferences(default_prefs, preferences)
        else:
            # Create new default preferences
            preferences = UserPreferences.create_default_preferences(user_id)
            db.session.add(preferences)
        
        db.session.commit()
        logger.info(f"Reset preferences to defaults for user {user_id}")
        
        return jsonify({
            'success': True,
            'data': preferences.to_dict(),
            'message': 'Preferences reset to defaults'
        }), 200
        
    except Exception as e:
        logger.error(f"Error resetting preferences for user {user_id}: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to reset user preferences'
        }), 500

@user_preferences_bp.route('/user/<int:user_id>/preferences/favorite-streamers', methods=['POST'])
@validate_user_id
def add_favorite_streamer(user_id, user):
    """Add a streamer to favorites"""
    try:
        data = request.get_json()
        if not data or 'streamer' not in data:
            return jsonify({'success': False, 'error': 'Streamer name is required'}), 400
        
        streamer_name = data['streamer'].strip().lower()
        if not streamer_name:
            return jsonify({'success': False, 'error': 'Invalid streamer name'}), 400
        
        preferences = UserPreferences.query.filter_by(user_id=user_id).first()
        if not preferences:
            preferences = UserPreferences.create_default_preferences(user_id)
            db.session.add(preferences)
        
        # Get current favorites
        favorites = preferences.get_favorite_streamers()
        
        # Add if not already in favorites (case-insensitive check)
        if streamer_name not in [fav.lower() for fav in favorites]:
            favorites.append(streamer_name)
            preferences.set_favorite_streamers(favorites)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'data': {'favorite_streamers': preferences.get_favorite_streamers()},
                'message': f'Added {streamer_name} to favorites'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Streamer already in favorites'
            }), 400
            
    except Exception as e:
        logger.error(f"Error adding favorite streamer for user {user_id}: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to add favorite streamer'
        }), 500

@user_preferences_bp.route('/user/<int:user_id>/preferences/favorite-streamers/<streamer_name>', methods=['DELETE'])
@validate_user_id
def remove_favorite_streamer(user_id, user, streamer_name):
    """Remove a streamer from favorites"""
    try:
        streamer_name = streamer_name.strip().lower()
        
        preferences = UserPreferences.query.filter_by(user_id=user_id).first()
        if not preferences:
            return jsonify({'success': False, 'error': 'User preferences not found'}), 404
        
        # Get current favorites
        favorites = preferences.get_favorite_streamers()
        
        # Remove streamer (case-insensitive)
        original_count = len(favorites)
        favorites = [fav for fav in favorites if fav.lower() != streamer_name]
        
        if len(favorites) < original_count:
            preferences.set_favorite_streamers(favorites)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'data': {'favorite_streamers': preferences.get_favorite_streamers()},
                'message': f'Removed {streamer_name} from favorites'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Streamer not found in favorites'
            }), 404
            
    except Exception as e:
        logger.error(f"Error removing favorite streamer for user {user_id}: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to remove favorite streamer'
        }), 500

def _update_preferences_from_data(preferences, data):
    """Helper function to update preferences from request data"""
    try:
        # Theme settings
        if 'theme' in data:
            if data['theme'] not in ['light', 'dark', 'auto']:
                return {'success': False, 'error': 'Invalid theme value'}
            preferences.theme = data['theme']
        
        # Auto-refresh settings
        if 'auto_refresh_enabled' in data:
            preferences.auto_refresh_enabled = bool(data['auto_refresh_enabled'])
        
        if 'auto_refresh_interval' in data:
            interval = int(data['auto_refresh_interval'])
            if interval < 5 or interval > 300:  # 5 seconds to 5 minutes
                return {'success': False, 'error': 'Auto-refresh interval must be between 5 and 300 seconds'}
            preferences.auto_refresh_interval = interval
        
        # Favorite streamers
        if 'favorite_streamers' in data:
            if isinstance(data['favorite_streamers'], list):
                # Validate streamer names
                streamers = [str(s).strip().lower() for s in data['favorite_streamers'] if str(s).strip()]
                if len(streamers) > 50:  # Limit to 50 favorites
                    return {'success': False, 'error': 'Too many favorite streamers (max 50)'}
                preferences.set_favorite_streamers(streamers)
            else:
                return {'success': False, 'error': 'favorite_streamers must be a list'}
        
        # Stream quality settings
        if 'preferred_stream_quality' in data:
            if data['preferred_stream_quality'] not in ['source', '1080p', '720p', '480p']:
                return {'success': False, 'error': 'Invalid stream quality value'}
            preferences.preferred_stream_quality = data['preferred_stream_quality']
        
        if 'auto_quality' in data:
            preferences.auto_quality = bool(data['auto_quality'])
        
        # Notification settings
        if 'notifications_enabled' in data:
            preferences.notifications_enabled = bool(data['notifications_enabled'])
        
        if 'notify_favorite_streamers' in data:
            preferences.notify_favorite_streamers = bool(data['notify_favorite_streamers'])
        
        if 'notify_leaderboard_changes' in data:
            preferences.notify_leaderboard_changes = bool(data['notify_leaderboard_changes'])
        
        if 'notify_new_clips' in data:
            preferences.notify_new_clips = bool(data['notify_new_clips'])
        
        return {'success': True}
        
    except (ValueError, TypeError) as e:
        return {'success': False, 'error': f'Invalid data format: {str(e)}'}

def _copy_preferences(source, target):
    """Helper function to copy preferences from source to target"""
    target.theme = source.theme
    target.auto_refresh_enabled = source.auto_refresh_enabled
    target.auto_refresh_interval = source.auto_refresh_interval
    target.favorite_streamers = source.favorite_streamers
    target.preferred_stream_quality = source.preferred_stream_quality
    target.auto_quality = source.auto_quality
    target.notifications_enabled = source.notifications_enabled
    target.notify_favorite_streamers = source.notify_favorite_streamers
    target.notify_leaderboard_changes = source.notify_leaderboard_changes
    target.notify_new_clips = source.notify_new_clips
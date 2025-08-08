import requests
import time
import json
import os
import secrets
from flask import Blueprint, jsonify, request, redirect, session
from urllib.parse import urlencode
from dotenv import load_dotenv

# Ensure test environment variables are loaded
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

twitch_oauth_bp = Blueprint('twitch_oauth', __name__)

# OAuth configuration
TWITCH_CLIENT_ID = os.environ.get('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.environ.get('TWITCH_CLIENT_SECRET')
# Default redirect URI for Vercel deployment
REDIRECT_URI = "https://live-leaderboard-plum.vercel.app/api/session/complete"

# Required scopes for clip creation
REQUIRED_SCOPES = "clips:edit"

# Persistent storage for OAuth states and tokens (Vercel-safe)
IS_SERVERLESS = bool(os.environ.get('VERCEL')) or '/var/task' in os.getcwd()

try:
    from vercel_cache import VercelCacheManager
    _cache = VercelCacheManager
except Exception:
    _cache = None

def load_oauth_data():
    """Load OAuth states and tokens using in-memory cache on Vercel, pickle locally."""
    if IS_SERVERLESS and _cache is not None:
        try:
            states = _cache.get('oauth_states', cache_type='access_tokens') or {}
            tokens = _cache.get('oauth_tokens', cache_type='access_tokens') or {}
            return states, tokens
        except Exception:
            return {}, {}
    # Local/dev fallback
    try:
        import pickle
        if os.path.exists('oauth_data.pkl'):
            with open('oauth_data.pkl', 'rb') as f:
                data = pickle.load(f)
                return data.get('states', {}), data.get('tokens', {})
        return {}, {}
    except Exception:
        return {}, {}

def save_oauth_data(states, tokens):
    """Save OAuth states and tokens using in-memory cache on Vercel, pickle locally."""
    if IS_SERVERLESS and _cache is not None:
        try:
            _cache.set('oauth_states', states, cache_type='access_tokens', ttl=3600)
            _cache.set('oauth_tokens', tokens, cache_type='access_tokens', ttl=3600)
            return
        except Exception as e:
            print(f"Warning: Could not cache OAuth data: {e}")
            return
    # Local/dev fallback
    try:
        import pickle
        with open('oauth_data.pkl', 'wb') as f:
            pickle.dump({'states': states, 'tokens': tokens}, f)
    except Exception as e:
        print(f"Warning: Could not save OAuth data: {e}")

# Load existing data
oauth_states, user_tokens = load_oauth_data()

@twitch_oauth_bp.route('/session/start')
def oauth_login():
    """Initiate OAuth flow for clip creation permissions"""
    from flask import request
    
    try:
        # Generate random state for CSRF protection
        state = secrets.token_urlsafe(32)
        oauth_states[state] = {
            'created_at': time.time(),
            'used': False
        }
        # Save the new state
        save_oauth_data(oauth_states, user_tokens)
        
        # Determine the correct redirect URI based on the current_url parameter
        current_url = request.args.get('current_url', '')
        if 'ngrok' in current_url or 'ngrok-free.app' in current_url:
            redirect_uri = "https://adapted-cunning-rhino.ngrok-free.app/api/session/complete"
        elif 'vercel.app' in current_url or 'live-leaderboard-plum.vercel.app' in current_url:
            redirect_uri = "https://live-leaderboard-plum.vercel.app/api/session/complete"
        else:
            redirect_uri = REDIRECT_URI
        
        # Build OAuth URL
        oauth_params = {
            'response_type': 'code',
            'client_id': TWITCH_CLIENT_ID,
            'redirect_uri': redirect_uri,
            'scope': REQUIRED_SCOPES,
            'state': state
        }
        
        oauth_url = f"https://id.twitch.tv/oauth2/authorize?{urlencode(oauth_params)}"
        
        return jsonify({
            'success': True,
            'oauth_url': oauth_url,
            'message': 'Redirect user to this URL to authorize clip creation'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to initiate OAuth: {str(e)}'
        }), 500

@twitch_oauth_bp.route('/session/complete')
def oauth_callback():
    """Handle OAuth callback from Twitch"""
    from flask import request
    
    try:
        # Get authorization code and state from callback
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        
        # Check for authorization errors
        if error:
            error_desc = request.args.get('error_description', 'Unknown error')
            return f"""
            <html><body>
                <h2>❌ Authorization Failed</h2>
                <p>Error: {error}</p>
                <p>Description: {error_desc}</p>
                <p><a href="javascript:window.close()">Close this window</a></p>
            </body></html>
            """, 400
        
        # Validate state parameter
        if not state or state not in oauth_states or oauth_states[state]['used']:
            return f"""
            <html><body>
                <h2>❌ Invalid Request</h2>
                <p>Invalid or expired state parameter</p>
                <p><a href="javascript:window.close()">Close this window</a></p>
            </body></html>
            """, 400
        
        # Mark state as used
        oauth_states[state]['used'] = True
        save_oauth_data(oauth_states, user_tokens)
        
        if not code:
            return f"""
            <html><body>
                <h2>❌ Authorization Failed</h2>
                <p>No authorization code received</p>
                <p><a href="javascript:window.close()">Close this window</a></p>
            </body></html>
            """, 400
        
        # Determine the correct redirect URI based on the current_url parameter
        current_url = request.args.get('current_url', '')
        if 'ngrok' in current_url or 'ngrok-free.app' in current_url:
            redirect_uri = "https://adapted-cunning-rhino.ngrok-free.app/api/session/complete"
        elif 'vercel.app' in current_url or 'live-leaderboard-plum.vercel.app' in current_url:
            redirect_uri = "https://live-leaderboard-plum.vercel.app/api/session/complete"
        else:
            redirect_uri = REDIRECT_URI
        
        # Exchange authorization code for access token
        token_data = {
            'client_id': TWITCH_CLIENT_ID,
            'client_secret': TWITCH_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri
        }
        
        token_response = requests.post(
            'https://id.twitch.tv/oauth2/token',
            data=token_data
        )
        
        if token_response.status_code != 200:
            return f"""
            <html><body>
                <h2>❌ Token Exchange Failed</h2>
                <p>Status: {token_response.status_code}</p>
                <p>Error: {token_response.text}</p>
                <p><a href="javascript:window.close()">Close this window</a></p>
            </body></html>
            """, 500
        
        token_info = token_response.json()
        access_token = token_info.get('access_token')
        refresh_token = token_info.get('refresh_token')
        
        if not access_token:
            return f"""
            <html><body>
                <h2>❌ No Access Token</h2>
                <p>Failed to receive access token from Twitch</p>
                <p><a href="javascript:window.close()">Close this window</a></p>
            </body></html>
            """, 500
        
        # Get user info to identify the authenticated user
        user_headers = {
            'Client-ID': TWITCH_CLIENT_ID,
            'Authorization': f'Bearer {access_token}'
        }
        
        user_response = requests.get('https://api.twitch.tv/helix/users', headers=user_headers)
        if user_response.status_code == 200:
            user_data = user_response.json()
            if user_data.get('data'):
                user_info = user_data['data'][0]
                username = user_info['login']
                display_name = user_info['display_name']
                
                # Store user token (in production, use database with encryption)
                user_tokens[username] = {
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'expires_in': token_info.get('expires_in', 3600),
                    'created_at': time.time(),
                    'username': username,
                    'display_name': display_name,
                    'scopes': token_info.get('scope', [])
                }
                # Save the new token
                save_oauth_data(oauth_states, user_tokens)
                
                # Success page
                return f"""
                <html><body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h2>✅ Authorization Successful!</h2>
                    <p>Welcome, <strong>{display_name}</strong>!</p>
                    <p>You can now create clips from live streams automatically.</p>
                    <p style="color: #666; font-size: 14px;">You can close this window and return to the multistream.</p>
                    <script>
                        // Try to notify parent window if opened as popup
                        if (window.opener) {{
                            window.opener.postMessage({{
                                type: 'twitch_oauth_success',
                                username: '{username}',
                                display_name: '{display_name}'
                            }}, '*');
                        }}
                        
                        // Auto-close after 3 seconds
                        setTimeout(() => {{
                            window.close();
                        }}, 3000);
                    </script>
                </body></html>
                """
        
        return f"""
        <html><body>
            <h2>⚠️ Authorization Incomplete</h2>
            <p>Token received but could not get user information</p>
            <p><a href="javascript:window.close()">Close this window</a></p>
        </body></html>
        """, 500
        
    except Exception as e:
        return f"""
        <html><body>
            <h2>❌ Server Error</h2>
            <p>Error: {str(e)}</p>
            <p><a href="javascript:window.close()">Close this window</a></p>
        </body></html>
        """, 500

@twitch_oauth_bp.route('/session/check')
def oauth_status():
    """Check if user has authorized clip creation"""
    try:
        username = request.args.get('username')
        if not username:
            return jsonify({
                'success': True,
                'authorized': False,
                'message': 'No username provided'
            })
        
        if username in user_tokens:
            token_info = user_tokens[username]
            # Check if token is still valid (simple expiry check)
            if time.time() - token_info['created_at'] < token_info['expires_in']:
                return jsonify({
                    'success': True,
                    'authorized': True,
                    'username': token_info['username'],
                    'display_name': token_info['display_name'],
                    'scopes': token_info['scopes']
                })
        
        return jsonify({
            'success': True,
            'authorized': False,
            'message': f'User {username} has not authorized clip creation'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def get_user_access_token(username):
    """Get user access token for a specific username"""
    if username in user_tokens:
        token_info = user_tokens[username]
        # Check if token is still valid
        if time.time() - token_info['created_at'] < token_info['expires_in']:
            return token_info['access_token']
    return None
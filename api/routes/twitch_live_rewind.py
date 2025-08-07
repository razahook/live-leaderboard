import requests
import json
import time
import re
import os
from flask import Blueprint, jsonify, request, Response, send_from_directory
from collections import deque
import threading
import hashlib
from datetime import datetime, timedelta
from routes.twitch_integration import get_twitch_access_token

twitch_live_rewind_bp = Blueprint('twitch_live_rewind', __name__)

# Global storage for live stream segments (in production use Redis/database)
live_stream_buffers = {}
stream_threads = {}

class LiveStreamBuffer:
    def __init__(self, channel_login, max_segments=300):  # ~5 minutes at 1s segments
        self.channel_login = channel_login
        self.segments = deque(maxlen=max_segments)
        self.is_recording = False
        self.thread = None
        self.m3u8_url = None
        self.last_update = time.time()
        self.segment_duration = 2  # Default segment duration in seconds
        self.total_duration = 0  # Total buffered duration
        
    def start_recording(self, m3u8_url):
        """Start buffering live stream segments"""
        if self.is_recording:
            return
            
        self.m3u8_url = m3u8_url
        self.is_recording = True
        self.thread = threading.Thread(target=self._record_segments)
        self.thread.daemon = True
        self.thread.start()
        
    def stop_recording(self):
        """Stop buffering segments"""
        self.is_recording = False
        if self.thread:
            self.thread.join(timeout=5)
            
    def _record_segments(self):
        """Background thread to continuously capture segments"""
        print(f"Started recording thread for {self.channel_login}")
        print(f"M3U8 URL: {self.m3u8_url}")
        
        while self.is_recording:
            try:
                # Fetch current M3U8 playlist
                print(f"Fetching M3U8 playlist for {self.channel_login}...")
                response = requests.get(self.m3u8_url, timeout=10)
                print(f"M3U8 response status: {response.status_code}")
                
                if response.status_code == 200:
                    playlist_content = response.text
                    print(f"M3U8 content length: {len(playlist_content)} chars")
                    
                    # Parse segment duration from M3U8
                    duration_match = re.search(r'#EXTINF:([\d.]+)', playlist_content)
                    if duration_match:
                        self.segment_duration = float(duration_match.group(1))
                        print(f"Segment duration: {self.segment_duration}s")
                    
                    # Parse segment URLs from M3U8
                    segment_urls = re.findall(r'https://[^\s]+\.ts', playlist_content)
                    print(f"Found {len(segment_urls)} segment URLs in playlist")
                    
                    if len(segment_urls) == 0:
                        print("No .ts segments found, playlist content:")
                        print(playlist_content[:500])
                    
                    new_segments_count = 0
                    current_time = time.time()
                    
                    # TRUE LIVE BUFFERING: Only capture the NEWEST segments as they become available
                    # On first run, only get the last 2-3 segments (most recent)
                    # On subsequent runs, only get segments we haven't seen before
                    
                    if len(self.segments) == 0:
                        # MAXIMUM FIRST RUN: Take last 30 segments for instant 60s+ buffer
                        # Live streams typically have 60+ segments in playlist, last 30 are still "live"
                        latest_segments = segment_urls[-30:] if len(segment_urls) >= 30 else segment_urls
                        print(f"MAXIMUM FIRST RUN: Taking {len(latest_segments)} segments for instant buffer (out of {len(segment_urls)} available)")
                    else:
                        # MAXIMUM UPDATES: Use FULL URL for duplicate detection
                        existing_urls = {seg['url'] for seg in self.segments}
                        new_segment_urls = [url for url in segment_urls if url not in existing_urls]
                        # Take ALL new segments - no limit
                        latest_segments = new_segment_urls
                        print(f"MAXIMUM UPDATE: Found {len(new_segment_urls)} new segments (from {len(segment_urls)} total), taking ALL")
                    
                    # PARALLEL DOWNLOAD for maximum speed
                    import concurrent.futures
                    
                    def download_segment(segment_url):
                        # Use full URL as unique identifier instead of just filename
                        segment_id = segment_url  # Full URL is truly unique
                        display_id = segment_url.split('/')[-1]  # For display purposes
                        try:
                            seg_response = requests.get(segment_url, timeout=5)  # Shorter timeout
                            if seg_response.status_code == 200:
                                return {
                                    'id': segment_id,  # Full URL for uniqueness
                                    'display_id': display_id,  # Short version for display
                                    'url': segment_url,
                                    'timestamp': current_time,
                                    'data': seg_response.content,
                                    'duration': self.segment_duration,
                                    'capture_time': current_time,
                                    'success': True
                                }
                        except Exception as e:
                            print(f"❌ Download failed for {display_id}: {e}")
                        return {'success': False, 'id': segment_id}
                    
                    # Download in parallel but maintain ORDER
                    segment_results = []
                    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                        # Submit all downloads
                        future_to_index = {executor.submit(download_segment, url): i for i, url in enumerate(latest_segments)}
                        
                        # Collect results with their original index
                        for future in concurrent.futures.as_completed(future_to_index):
                            result = future.result()
                            if result['success']:
                                original_index = future_to_index[future]
                                segment_results.append((original_index, result))
                    
                    # Sort by original index to maintain chronological order
                    segment_results.sort(key=lambda x: x[0])
                    
                    # Add segments in correct order
                    for _, segment_data in segment_results:
                        self.segments.append(segment_data)
                        new_segments_count += 1
                        print(f"✅ ORDERED capture: {segment_data['id']} ({len(segment_data['data'])} bytes)")
                    
                    print(f"🚀 SPEED DOWNLOAD: Captured {new_segments_count} segments in correct order")
                    
                    # Update total duration - calculate actual duration from segments
                    if len(self.segments) > 0:
                        self.total_duration = len(self.segments) * self.segment_duration
                        print(f"Updated total duration: {self.total_duration}s from {len(self.segments)} segments")
                    else:
                        self.total_duration = 0
                    self.last_update = time.time()
                    
                    if new_segments_count > 0:
                        print(f"Captured {new_segments_count} new segments for {self.channel_login} (Total: {len(self.segments)} segments, ~{self.total_duration:.1f}s)")
                    else:
                        print(f"No new segments added. Total segments: {len(self.segments)}")
                else:
                    print(f"Failed to fetch M3U8 playlist: {response.status_code}")
                    print(f"Response: {response.text[:200]}")
                    
                time.sleep(0.5)  # Check for new segments every 500ms (maximum speed)
                
            except Exception as e:
                print(f"Error recording segments for {self.channel_login}: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)  # Wait longer on error
                
    def get_rewind_segments(self, seconds_back=60):
        """Get segments from X seconds ago"""
        cutoff_time = time.time() - seconds_back
        available_segments = [seg for seg in self.segments if seg['timestamp'] >= cutoff_time]
        
        # Calculate actual available rewind time
        available_rewind_time = len(available_segments) * self.segment_duration
        
        return {
            'segments': available_segments,
            'requested_seconds': seconds_back,
            'available_seconds': available_rewind_time,
            'segments_count': len(available_segments),
            'total_buffered': self.total_duration
        }

@twitch_live_rewind_bp.route('/stream-live-streamers', methods=['GET'])
def get_live_streamers():
    """Get currently live streamers using Twitch API"""
    try:
        access_token = get_twitch_access_token()
        if not access_token:
            return jsonify({
                'success': False,
                'error': 'Failed to get Twitch access token'
            }), 500
            
        client_id = os.environ.get('TWITCH_CLIENT_ID')
        if not client_id:
            return jsonify({
                'success': False,
                'error': 'TWITCH_CLIENT_ID not configured'
            }), 500
            
        headers = {
            'Client-Id': client_id,
            'Authorization': f'Bearer {access_token}'
        }
        
        # Get top live streams
        streams_response = requests.get(
            'https://api.twitch.tv/helix/streams?first=20&language=en', 
            headers=headers, 
            timeout=10
        )
        
        if streams_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': f'Failed to get live streams: {streams_response.status_code}'
            }), 500
            
        streams_data = streams_response.json().get('data', [])
        
        live_streamers = []
        for stream in streams_data:
            # Clean title of emojis that cause encoding issues
            title = stream['title']
            # Remove common problematic characters
            title = title.encode('ascii', 'ignore').decode('ascii')
            
            # Also clean display name and game name
            display_name = stream['user_name'].encode('ascii', 'ignore').decode('ascii')
            game_name = stream['game_name'].encode('ascii', 'ignore').decode('ascii')
            
            live_streamers.append({
                'login': stream['user_login'],
                'display_name': display_name,
                'title': title,
                'game_name': game_name,
                'viewer_count': stream['viewer_count'],
                'language': stream['language'],
                'thumbnail_url': stream['thumbnail_url']
            })
            
        return jsonify({
            'success': True,
            'streamers': live_streamers,
            'count': len(live_streamers),
            'message': f'Found {len(live_streamers)} live streamers'
        })
        
    except Exception as e:
        print(f"Error getting live streamers: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_live_rewind_bp.route('/stream-live-stream/<channel_login>', methods=['POST'])
def get_live_stream_info(channel_login):
    """Get live stream M3U8 URL for a channel"""
    try:
        print(f"Getting live stream info for: {channel_login}")
        
        # Get tokens from request
        data = request.get_json() or {}
        tokens = data.get('tokens', {})
        
        # First check if the stream is actually live using Helix API
        access_token = get_twitch_access_token()
        if not access_token:
            return jsonify({
                'success': False,
                'error': 'Failed to get Twitch access token'
            }), 500
            
        client_id = os.environ.get('TWITCH_CLIENT_ID')
        if not client_id:
            return jsonify({
                'success': False,
                'error': 'TWITCH_CLIENT_ID not configured'
            }), 500
            
        helix_headers = {
            'Client-Id': client_id,
            'Authorization': f'Bearer {access_token}'
        }
        
        # Get user ID first
        user_response = requests.get(f"https://api.twitch.tv/helix/users?login={channel_login}", 
                                   headers=helix_headers, timeout=10)
        if user_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': 'Failed to get user info'
            }), 500
            
        user_data = user_response.json().get('data', [])
        if not user_data:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
            
        user_id = user_data[0]['id']
        
        # Check if stream is live
        stream_response = requests.get(f"https://api.twitch.tv/helix/streams?user_id={user_id}", 
                                     headers=helix_headers, timeout=10)
        if stream_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': 'Failed to get stream info'
            }), 500
            
        stream_data = stream_response.json().get('data', [])
        if not stream_data:
            return jsonify({
                'success': False,
                'error': f'{channel_login} is not currently live'
            }), 404
            
        # Clean title for safe printing
        stream_title = stream_data[0]['title'].encode('ascii', 'ignore').decode('ascii')
        print(f"Stream confirmed live: {stream_title}")
        
        # Twitch GQL query to get live stream info
        gql_url = "https://gql.twitch.tv/gql"
        gql_payload = {
            "operationName": "PlaybackAccessToken",
            "variables": {
                "isLive": True,
                "login": channel_login,
                "isVod": False,
                "vodID": "",
                "playerType": "site"
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "0828119ded1c13477966434e15800ff57ddacf13ba1911c129dc2200705b0712"
                }
            }
        }
        
        gql_headers = {
            'accept': '*/*',
            'accept-language': 'en-US',
            'authorization': 'OAuth 776n9yzyvxcdul878r2lszi7b7ma6q',
            'client-id': 'kimne78kx3ncx6brgo4mv6wki5h1ko',
            'content-type': 'text/plain;charset=UTF-8',
            'origin': 'https://www.twitch.tv',
            'referer': 'https://www.twitch.tv/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
        }
        
        # Override with custom tokens if provided
        if tokens.get('authorization'):
            gql_headers['authorization'] = tokens['authorization']
        if tokens.get('client_id'):
            gql_headers['client-id'] = tokens['client_id']
            
        response = requests.post(gql_url, json=gql_payload, headers=gql_headers, timeout=10)
        
        if response.status_code != 200:
            return jsonify({
                'success': False,
                'error': f'Failed to get stream token: {response.status_code}'
            }), 500
            
        response_data = response.json()
        print(f"GQL Response: {response_data}")
        
        if 'data' not in response_data:
            return jsonify({
                'success': False,
                'error': f'No data in response: {response_data}'
            }), 500
            
        token_data = response_data['data']['streamPlaybackAccessToken']
        if not token_data:
            return jsonify({
                'success': False,
                'error': 'Stream is offline or not accessible'
            }), 404
            
        # Get M3U8 playlist URL
        access_token = token_data['value']
        signature = token_data['signature']
        
        m3u8_url = f"https://usher.ttvnw.net/api/channel/hls/{channel_login}.m3u8"
        m3u8_params = {
            'client_id': gql_headers['client-id'],
            'token': access_token,
            'sig': signature,
            'allow_source': 'true',
            'allow_audio_only': 'true',
            'allow_spectre': 'false',
            'p': '1234567',
            'play_session_id': hashlib.md5(f"{channel_login}{time.time()}".encode()).hexdigest()
        }
        
        # Fetch the master playlist
        print(f"Fetching M3U8 from: {m3u8_url}")
        print(f"M3U8 params: {m3u8_params}")
        m3u8_response = requests.get(m3u8_url, params=m3u8_params, timeout=10)
        print(f"M3U8 response status: {m3u8_response.status_code}")
        if m3u8_response.status_code != 200:
            print(f"M3U8 error response: {m3u8_response.text[:200]}")
            return jsonify({
                'success': False,
                'error': f'Failed to fetch M3U8 playlist: {m3u8_response.status_code}'
            }), 500
            
        # Parse quality options from master playlist
        playlist_content = m3u8_response.text
        print(f"Master playlist content preview: {playlist_content[:500]}")
        
        quality_urls = {}
        lines = playlist_content.split('\n')
        
        # Parse M3U8 master playlist
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith('#EXT-X-STREAM-INF'):
                # Look for the URL on the next line
                if i + 1 < len(lines):
                    url = lines[i + 1].strip()
                    if url.startswith('https://'):
                        # Extract quality info
                        name_match = re.search(r'NAME="([^"]+)"', line)
                        resolution_match = re.search(r'RESOLUTION=(\d+x\d+)', line)
                        
                        if name_match:
                            quality_name = name_match.group(1)
                        elif resolution_match:
                            resolution = resolution_match.group(1)
                            if '1920x1080' in resolution:
                                quality_name = '1080p60 (source)'
                            elif '1280x720' in resolution:
                                quality_name = '720p60'
                            elif '854x480' in resolution:
                                quality_name = '480p'
                            elif '640x360' in resolution:
                                quality_name = '360p'
                            else:
                                quality_name = f"{resolution}"
                        else:
                            quality_name = f"Quality_{len(quality_urls)}"
                            
                        quality_urls[quality_name] = url
                        print(f"Found quality: {quality_name} -> {url[:50]}...")
        
        # Fallback: if no stream-inf found, look for direct URLs
        if not quality_urls:
            for line in lines:
                line = line.strip()
                if line.startswith('https://') and '.m3u8' in line:
                    quality_urls[f"Stream_{len(quality_urls)}"] = line
                    print(f"Found direct stream: {line[:50]}...")
        
        print(f"Total qualities found: {len(quality_urls)}")
        
        # Default to source quality (usually the first/highest quality)
        source_url = None
        if quality_urls:
            # Try to get source/highest quality first
            for key in ['1080p60 (source)', 'Source', '1080p60', '720p60']:
                if key in quality_urls:
                    source_url = quality_urls[key]
                    break
            
            # If no preferred quality found, get the first one
            if not source_url:
                source_url = list(quality_urls.values())[0]
                
        print(f"Selected source URL: {source_url[:100] if source_url else 'None'}...")
            
        # AUTO-START BUFFERING like Twitch clips!
        print(f"Auto-starting buffer for {channel_login}...")
        
        # Create buffer immediately
        if channel_login not in live_stream_buffers:
            live_stream_buffers[channel_login] = LiveStreamBuffer(channel_login, max_segments=150)  # 5-minute rolling buffer
            print(f"Created auto-buffer for: {channel_login}")
        
        buffer = live_stream_buffers[channel_login]
        buffer.start_recording(source_url)
        print(f"Auto-buffering started for: {channel_login}")
        
        return jsonify({
            'success': True,
            'channel': channel_login,
            'is_live': True,
            'source_m3u8': source_url,
            'quality_options': quality_urls,
            'access_token': access_token[:50] + '...',  # Truncated for security
            'auto_buffering': True,
            'buffer_duration': '5 minutes',
            'message': 'Live stream ready! Auto-buffering started - clips available anytime!'
        })
        
    except Exception as e:
        print(f"Error getting live stream: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_live_rewind_bp.route('/twitch/start-buffer/<channel_login>', methods=['POST'])
def start_live_buffer(channel_login):
    """Start buffering live stream segments for rewinding"""
    try:
        data = request.get_json() or {}
        m3u8_url = data.get('m3u8_url')
        
        if not m3u8_url:
            return jsonify({
                'success': False,
                'error': 'M3U8 URL required'
            }), 400
            
        # Create or get existing buffer
        if channel_login not in live_stream_buffers:
            live_stream_buffers[channel_login] = LiveStreamBuffer(channel_login)
            print(f"Created new buffer for: {channel_login}")
        else:
            print(f"Using existing buffer for: {channel_login}")
            
        buffer = live_stream_buffers[channel_login]
        buffer.start_recording(m3u8_url)
        
        print(f"Buffer started for: {channel_login}")
        print(f"Current buffers: {list(live_stream_buffers.keys())}")
        
        return jsonify({
            'success': True,
            'message': f'Started buffering live stream for {channel_login}',
            'buffer_size': len(buffer.segments)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_live_rewind_bp.route('/twitch/rewind/<channel_login>/<int:seconds>', methods=['GET'])
def rewind_stream(channel_login, seconds):
    """Get segments from X seconds ago for rewinding"""
    try:
        print(f"Rewind request for: {channel_login}")
        print(f"Available buffers: {list(live_stream_buffers.keys())}")
        print(f"Total buffers: {len(live_stream_buffers)}")
        
        if channel_login not in live_stream_buffers:
            return jsonify({
                'success': False,
                'error': f'No buffer found for this channel. Available: {list(live_stream_buffers.keys())}'
            }), 404
            
        buffer = live_stream_buffers[channel_login]
        rewind_data = buffer.get_rewind_segments(seconds)
        
        return jsonify({
            'success': True,
            'channel': channel_login,
            'requested_rewind_seconds': seconds,
            'available_rewind_seconds': rewind_data['available_seconds'],
            'segments_available': rewind_data['segments_count'],
            'total_buffered_duration': rewind_data['total_buffered'],
            'segment_duration': buffer.segment_duration,
            'segments': [{'id': s['id'], 'timestamp': s['timestamp'], 'duration': s.get('duration', 2)} for s in rewind_data['segments']],
            'message': f"Available rewind: {rewind_data['available_seconds']:.1f}s (requested: {seconds}s)"
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_live_rewind_bp.route('/stream-create-clip/<channel_login>', methods=['POST'])
def create_clip_from_buffer(channel_login):
    """Create a clip from buffered segments"""
    try:
        print(f"Clip request for: {channel_login}")
        print(f"Available buffers: {list(live_stream_buffers.keys())}")
        
        data = request.get_json() or {}
        start_seconds = data.get('start_seconds', 60)  # How far back to start
        duration = data.get('duration', 30)  # Clip duration
        
        print(f"Clip parameters: start_seconds={start_seconds}, duration={duration}")
        
        if channel_login not in live_stream_buffers:
            return jsonify({
                'success': False,
                'error': 'No buffer found for this channel'
            }), 404
            
        buffer = live_stream_buffers[channel_login]
        
        print(f"Buffer has {len(buffer.segments)} total segments")
        print(f"Buffer is_recording: {buffer.is_recording}")
        print(f"Last 3 segment IDs: {[seg['id'][-6:] for seg in list(buffer.segments)[-3:]]}")
        
        # Get segments for the clip
        # Fix: Calculate time range correctly for "X seconds ago" logic
        now = time.time()
        end_time = now - start_seconds  # "start_seconds ago" is the END of our clip
        start_time = end_time - duration  # Go back "duration" more for the START
        
        print(f"Clip timing: {start_seconds}s ago for {duration}s duration")
        print(f"Time range: {start_time} to {end_time} (now: {now})")
        
        # Get segments within the time range, sorted by timestamp
        clip_segments = [
            seg for seg in buffer.segments 
            if start_time <= seg['timestamp'] <= end_time
        ]
        
        # Sort segments by timestamp to ensure proper order
        clip_segments.sort(key=lambda x: x['timestamp'])
        
        print(f"Found {len(clip_segments)} segments for clip")
        if clip_segments:
            first_seg_time = clip_segments[0]['timestamp']
            last_seg_time = clip_segments[-1]['timestamp']
            actual_duration = last_seg_time - first_seg_time
            print(f"Actual clip spans: {actual_duration:.1f}s (requested: {duration}s)")
        
        if not clip_segments:
            # Debug: Show what segments we DO have
            debug_info = []
            current_time = time.time()
            for seg in list(buffer.segments)[-10:]:  # Last 10 segments
                seconds_ago = current_time - seg['timestamp']
                debug_info.append(f"{seg['id'][-6:]}: {seconds_ago:.1f}s ago")
            
            return jsonify({
                'success': False,
                'error': f'No segments available for the requested time range. Requested: {start_seconds}s ago for {duration}s. Available segments: {debug_info}. Time range searched: {start_time:.1f} to {end_time:.1f} (now: {now:.1f})'
            }), 404
            
        # Create actual clip file by stitching segments
        clip_id = hashlib.md5(f"{channel_login}{start_time}{duration}".encode()).hexdigest()[:12]
        
        # Create clips directory if it doesn't exist
        clips_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'clips')
        os.makedirs(clips_dir, exist_ok=True)
        
        clip_filename = f"clip_{clip_id}_{channel_login}.ts"
        clip_path = os.path.join(clips_dir, clip_filename)
        
        # Stitch segments together by concatenating the .ts files
        print(f"Creating clip file: {clip_path}")
        with open(clip_path, 'wb') as clip_file:
            for segment in clip_segments:
                clip_file.write(segment['data'])
                
        print(f"Clip created successfully: {clip_filename} ({os.path.getsize(clip_path)} bytes)")
        
        # Generate download URL
        clip_url = f"/clips/{clip_filename}"
        
        # Calculate actual clip timing
        actual_duration = 0
        if clip_segments:
            first_seg_time = clip_segments[0]['timestamp']
            last_seg_time = clip_segments[-1]['timestamp']
            actual_duration = last_seg_time - first_seg_time + clip_segments[-1]['duration']
        
        return jsonify({
            'success': True,
            'clip_id': clip_id,
            'channel': channel_login,
            'requested_start_seconds': start_seconds,
            'requested_duration': duration,
            'actual_duration': round(actual_duration, 1),
            'segments_count': len(clip_segments),
            'clip_filename': clip_filename,
            'clip_url': clip_url,
            'file_size': os.path.getsize(clip_path),
            'message': f'Clip created! Requested: {duration}s, Actual: {actual_duration:.1f}s',
            'timing_note': f'Clip ends {start_seconds}s ago, spans {actual_duration:.1f}s backwards from that point'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_live_rewind_bp.route('/stream-buffer-status/<channel_login>', methods=['GET'])
def get_buffer_status(channel_login):
    """Get current buffer status for a channel"""
    try:
        if channel_login not in live_stream_buffers:
            return jsonify({
                'success': True,
                'channel': channel_login,
                'is_buffering': False,
                'segments_count': 0,
                'buffer_duration': 0,
                'segment_duration': 0,
                'total_duration': 0
            })
            
        buffer = live_stream_buffers[channel_login]
        
        # Add debug info about segment timing
        debug_segments = []
        current_time = time.time()
        for seg in list(buffer.segments)[-5:]:  # Last 5 segments for debugging
            seconds_ago = current_time - seg['timestamp']
            # Get a more unique part of the segment ID
            segment_id = seg['id']
            if len(segment_id) > 20:
                display_id = segment_id[-20:]  # Last 20 chars
            else:
                display_id = segment_id
            debug_segments.append({
                'id': display_id,
                'seconds_ago': round(seconds_ago, 1),
                'duration': seg['duration']
            })
        
        # Force recalculate total duration to make sure it's correct
        calculated_duration = len(buffer.segments) * buffer.segment_duration
        buffer.total_duration = calculated_duration
        
        print(f"Buffer status for {channel_login}:")
        print(f"  Segments: {len(buffer.segments)}")  
        print(f"  Segment duration: {buffer.segment_duration}s")
        print(f"  Calculated duration: {calculated_duration}s")
        print(f"  Buffer.total_duration: {buffer.total_duration}s")
        
        return jsonify({
            'success': True,
            'channel': channel_login,
            'is_buffering': buffer.is_recording,
            'segments_count': len(buffer.segments),
            'buffer_duration': calculated_duration,
            'segment_duration': buffer.segment_duration,
            'total_duration': calculated_duration,
            'last_update': buffer.last_update,
            'max_rewind_available': f"{calculated_duration:.1f} seconds",
            'debug_latest_segments': debug_segments  # Debug info
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_live_rewind_bp.route('/twitch/stop-buffer/<channel_login>', methods=['POST'])
def stop_live_buffer(channel_login):
    """Stop buffering for a channel"""
    try:
        if channel_login in live_stream_buffers:
            buffer = live_stream_buffers[channel_login]
            buffer.stop_recording()
            del live_stream_buffers[channel_login]
            
        return jsonify({
            'success': True,
            'message': f'Stopped buffering for {channel_login}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_live_rewind_bp.route('/clips/<filename>')
def serve_clip(filename):
    """Serve clip files for download"""
    try:
        clips_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'clips')
        return send_from_directory(clips_dir, filename, as_attachment=True)
    except Exception as e:
        return jsonify({'error': 'Clip not found'}), 404
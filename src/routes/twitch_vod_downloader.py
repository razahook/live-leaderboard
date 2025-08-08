import requests
import json
import time
import hashlib
import re
from flask import Blueprint, jsonify, request
from urllib.parse import urlparse, parse_qs
import os
from bs4 import BeautifulSoup

twitch_vod_bp = Blueprint('twitch_vod', __name__)

# Twitch API configuration
TWITCH_CLIENT_ID = os.environ.get('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.environ.get('TWITCH_CLIENT_SECRET')

# CloudFront server IDs from the extension
CLOUDFRONT_SERVERS = [
    "d2vjef5jvl6bfs",
    "d1ymi26ma8va5x", 
    "d2e2de1etea730",
    "dqrpb9wgowsf5",
    "ds0h3roq6wcgc",
    "d2nvs31859zcd8",
    "d2aba1wr3818hz",
    "d3c27h4odz752x",
    "dgeft87wbj63p",
    "d1m7jfoe9zdc1j",
    "d3vd9lfkzbru3h",
    "d1mhjrowxxagfy",
    "ddacn6pr5v0tl",
    "d3aqoihi2n8ty8",
]

def sha1_hash(text):
    """Generate SHA1 hash like the extension does"""
    return hashlib.sha1(text.encode('utf-8')).hexdigest().lower()

def construct_m3u8_url(channel_login, stream_id, timestamp_seconds, server_id):
    """Construct M3U8 URL exactly like the extension does"""
    # Generate hash: SHA1(channel_login_stream_id_timestamp).slice(0, 20)
    hash_input = f"{channel_login}_{stream_id}_{timestamp_seconds}"
    hash_value = sha1_hash(hash_input)[:20]
    
    # Build URL: https://{server}.cloudfront.net/{hash}_{channel}_{stream_id}_{timestamp}/chunked/index-dvr.m3u8
    url = f"https://{server_id}.cloudfront.net/{hash_value}_{channel_login}_{stream_id}_{timestamp_seconds}/chunked/index-dvr.m3u8"
    return url, hash_value

def test_m3u8_url(url):
    """Test if an M3U8 URL is working by checking for valid playlist content"""
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            # Check if it contains .ts file references (valid M3U8 playlist)
            if re.search(r'[\d\.]+,\n\d+(-\w+|\b)\.ts', response.text):
                return True
        return False
    except:
        return False

def find_working_m3u8_url(channel_login, stream_id, timestamp_seconds):
    """Find working M3U8 URL by testing multiple servers and time offsets like the extension"""
    print(f"Searching for M3U8 URL: {channel_login}_{stream_id}_{timestamp_seconds}")
    
    # Test exact timestamp first
    for server_id in CLOUDFRONT_SERVERS:  # Test all servers
        url, hash_value = construct_m3u8_url(channel_login, stream_id, timestamp_seconds, server_id)
        if test_m3u8_url(url):
            print(f"SUCCESS: Found working M3U8 at {server_id}")
            return {
                'source_url': url,
                'hash': hash_value,
                'm3u8_server': server_id,
                'm3u8_path': f"{server_id}.cloudfront.net/{hash_value}_{channel_login}_{stream_id}_{timestamp_seconds}"
            }
    
    # Test with time offsets (+/- 61 seconds like extension)
    for offset in [61, -61]:  # Try +61 then -61 seconds
        test_timestamp = timestamp_seconds + offset
        for server_id in CLOUDFRONT_SERVERS:
            url, hash_value = construct_m3u8_url(channel_login, stream_id, test_timestamp, server_id)
            if test_m3u8_url(url):
                print(f"SUCCESS: Found working M3U8 at {server_id} with offset {offset}s")
                return {
                    'source_url': url,
                    'hash': hash_value,
                    'm3u8_server': server_id,
                    'm3u8_path': f"{server_id}.cloudfront.net/{hash_value}_{channel_login}_{stream_id}_{test_timestamp}",
                    'timestamp_offset': offset
                }
    
    print(f"FAILED: No working M3U8 URL found")
    return None

def get_twitch_access_token():
    """Get Twitch access token"""
    try:
        print(f"Getting Twitch access token with Client-ID: {TWITCH_CLIENT_ID[:10]}...")
        url = "https://id.twitch.tv/oauth2/token"
        data = {
            'client_id': TWITCH_CLIENT_ID,
            'client_secret': TWITCH_CLIENT_SECRET,
            'grant_type': 'client_credentials'
        }
        response = requests.post(url, data=data)
        response.raise_for_status()
        token_data = response.json()
        token = token_data.get('access_token')
        if token:
            print(f"Successfully got access token: {token[:20]}...")
        else:
            print(f"Unexpected token response: {token_data}")
        return token
    except Exception as e:
        print(f"Error getting Twitch access token: {e}")
        return None

def get_twitch_headers():
    """Get headers for Twitch API requests"""
    token = get_twitch_access_token()
    if not token:
        raise Exception("Failed to get Twitch access token")
    
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    print(f"Headers created with Client-ID: {TWITCH_CLIENT_ID[:10]}... and token: {token[:20]}...")
    return headers

def get_sully_streams_data(channel_login):
    """Scrape recent stream data from SullyGnome like the extension does"""
    try:
        print(f"Scraping SullyGnome for channel: {channel_login}")
        
        # Use hardcoded channel ID for nv_messiah (like the working test)
        if channel_login.lower() == 'nv_messiah':
            channel_id = '30130953'
            print(f"Using hardcoded channel ID for {channel_login}: {channel_id}")
        else:
            print(f"Channel {channel_login} not supported yet (only nv_messiah)")
            return []
        
        # Make API call using same pattern as the working test script - get all 85 streams
        api_url = f"https://sullygnome.com/api/tables/channeltables/streams/90/{channel_id}/%20/1/1/desc/0/85"
        print(f"Fetching API data: {api_url}")
        
        # Use exact same headers as the working test script
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': f'https://sullygnome.com/channel/{channel_login}/30/streams',
            'X-Requested-With': 'XMLHttpRequest',
            'DNT': '1',
            'Connection': 'keep-alive',
        }
        
        api_response = requests.get(api_url, headers=headers, timeout=15)
        print(f"API Response status: {api_response.status_code}")
        
        if api_response.status_code != 200:
            print(f"ERROR: SullyGnome API failed with status {api_response.status_code}")
            return []
        
        print("SUCCESS: SullyGnome API request successful!")
        
        # Fix encoding issue with non-ASCII characters in SullyGnome response
        api_response.encoding = 'utf-8'
        data = api_response.json()
        
        # Parse the stream data like the extension does
        raw_data = data.get('data', [])
        print(f"Raw SullyGnome API data count: {len(raw_data)}")
        if len(raw_data) > 0:
            print(f"First stream sample: streamId={raw_data[0].get('streamId')}, length={raw_data[0].get('length')}")
        
        parsed_streams = []
        for stream in raw_data:
            try:
                start_datetime = stream.get('startDateTime')
                if start_datetime:
                    # Use correct datetime format for SullyGnome API response
                    from datetime import datetime
                    timestamp = int(datetime.strptime(start_datetime, "%Y-%m-%dT%H:%M:%SZ").timestamp() * 1000)
                    
                    # Extract stream_id from SullyGnome data (streamId field)
                    stream_id = str(stream.get('streamId', '')) if stream.get('streamId') else None
                    
                    # Try to find working M3U8 URL for this SullyGnome stream
                    m3u8_data = find_working_m3u8_url(channel_login, stream_id, timestamp // 1000)
                    
                    parsed_stream = {
                        'duration': (stream.get('length', 0) * 60000) if stream.get('length') else 0,  # Convert to milliseconds
                        'channel_login': stream.get('channelurl', channel_login),
                        'stream_id': stream_id,
                        'timestamp': timestamp,
                        'timestamp_seconds': timestamp // 1000,
                        'title': f"Stream {stream_id}",  # SullyGnome doesn't provide titles, use stream ID
                        'startDateTime': start_datetime,
                    }
                    
                    # Add M3U8 data if found
                    if m3u8_data:
                        parsed_stream.update({
                            'source_url': m3u8_data['source_url'],
                            'hash': m3u8_data['hash'],
                            'm3u8_server': m3u8_data['m3u8_server'],
                            'm3u8_path': m3u8_data['m3u8_path'],
                            'is_hidden': True,
                            'has_m3u8': True
                        })
                        if 'timestamp_offset' in m3u8_data:
                            parsed_stream['timestamp_offset'] = m3u8_data['timestamp_offset']
                        print(f"SUCCESS: Parsed stream {stream_id} WITH M3U8 URL")
                    else:
                        parsed_stream['has_m3u8'] = False
                        print(f"SUCCESS: Parsed stream {stream_id} without M3U8 URL")
                    
                    # Only add if we have essential data
                    if stream_id and timestamp:
                        parsed_streams.append(parsed_stream)
                    else:
                        print(f"SKIPPED: missing stream_id={stream_id} or timestamp={timestamp}")
                        
            except Exception as e:
                print(f"Error parsing stream: {e}")
                continue
        
        print(f"Found {len(parsed_streams)} recent streams from SullyGnome")
        return parsed_streams
        
    except Exception as e:
        print(f"Error scraping SullyGnome: {e}")
        import traceback
        print("Full traceback:")
        traceback.print_exc()
        return []

def merge_vods_with_sully_gnome(sully_data, vods):
    """Merge SullyGnome stream data with VOD data like the extension does"""
    print(f"Merging {len(sully_data)} sully streams with {len(vods)} VODs")
    
    # Match Sully streams with VODs by stream_id
    sully_matched = []
    for sully_stream in sully_data:
        matching_vod = None
        for vod in vods:
            if str(vod.get('stream_id')) == str(sully_stream.get('stream_id')):
                matching_vod = vod
                break
        
        if matching_vod:
            # Merge sully data with VOD data
            merged = {**sully_stream, **matching_vod}
            sully_matched.append(merged)
        else:
            # Keep sully stream even without VOD match
            sully_matched.append(sully_stream)
    
    # Also add VODs that didn't match any sully stream
    vod_matched = []
    for vod in vods:
        matching_sully = None
        for sully_stream in sully_data:
            if str(vod.get('stream_id')) == str(sully_stream.get('stream_id')):
                matching_sully = sully_stream
                break
        
        if matching_sully:
            # Already added in sully_matched above
            pass
        else:
            # Add VOD without sully match
            vod_matched.append(vod)
    
    # Combine and deduplicate by stream_id
    all_streams = sully_matched + vod_matched
    
    # Remove duplicates by stream_id and sort by timestamp (newest first)
    seen_stream_ids = set()
    unique_streams = []
    for stream in sorted(all_streams, key=lambda x: x.get('timestamp', 0), reverse=True):
        stream_id = stream.get('stream_id')
        if stream_id and stream_id not in seen_stream_ids:
            seen_stream_ids.add(stream_id)
            unique_streams.append(stream)
    
    # Return all streams without date filtering
    print(f"Final merged result: {len(unique_streams)} total streams")
    return unique_streams

@twitch_vod_bp.route('/stream-search', methods=['POST'])
def search_twitch():
    """Search Twitch channels and streams"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        
        headers = get_twitch_headers()
        
        # Search for channels
        channel_url = f"https://api.twitch.tv/helix/search/channels?query={query}&first=10"
        channel_response = requests.get(channel_url, headers=headers)
        channel_response.raise_for_status()
        channels = channel_response.json().get('data', [])
        
        # Search for streams
        stream_url = f"https://api.twitch.tv/helix/search/channels?query={query}&first=10"
        stream_response = requests.get(stream_url, headers=headers)
        stream_response.raise_for_status()
        streams = stream_response.json().get('data', [])
        
        return jsonify({
            'success': True,
            'channels': channels,
            'streams': streams
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_vod_bp.route('/stream-channel/<channel_login>', methods=['GET'])
def get_channel_info(channel_login):
    """Get channel information"""
    try:
        headers = get_twitch_headers()
        url = f"https://api.twitch.tv/helix/users?login={channel_login}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        user_data = response.json().get('data', [])
        if not user_data:
            return jsonify({'success': False, 'error': 'Channel not found'}), 404
        
        return jsonify({
            'success': True,
            'channel': user_data[0]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_vod_bp.route('/twitch/videos/<channel_login>', methods=['GET'])
def get_channel_videos(channel_login):
    """Get channel videos/VODs including hidden ones using GQL"""
    try:
        print(f"Getting VODs for channel: {channel_login}")
        
        # Use GQL to get VODs (including hidden ones)
        gql_url = "https://gql.twitch.tv/gql"
        gql_payload = [{
            "operationName": "FilterableVideoTower_Videos",
            "variables": {
                "limit": 100,  # Reasonable limit to avoid blocks
                "channelOwnerLogin": channel_login,
                "broadcastType": "ARCHIVE",
                "videoSort": "TIME"
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "a937f1d22e269e39a03b509f65a7490f9fc247d7f83d6ac1421523e3b68042cb"
                }
            }
        }]
        
        # GQL headers (matching the extension exactly)
        gql_headers = {
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'en-US',
            'client-id': 'kimne78kx3ncx6brgo4mv6wki5h1ko',
            'client-integrity': 'v4.local.EOvZGU3SI2Z3hQOEHt4NJvAW7hnpgb6RTghw6yw3K0PeQbs_sCoNV8gKG5T5Jd-xD5HRHF41chxNRh84-5KllcgxU46HzZxPtKye386WQVFVIjmTBrauqq5fEHZmok7O9kXMQvMhRDYTaEVuXK2rdwCo-lGT4K6wPEMxDU6TF0PCPXnaWy2R8xdvqZ5kdGLKRDvyaszTVxpr8wlFiL6Q5VKAQyIDXUYvfuyAx2Pcs3KDryMIwn2UsSbMAxTWVPgtbRad-3QynJ3tnDfs9LaQnteHeDueWg0mMPPqyCGoXIN7BAVcfMhqt9hdPsOuo2YNKOxN2FWx0AOWXe487zR56I3ge1lu00OfDY5JdRXCvXciqZ2ozQxNqDmuVwKj4wV-MVZGTYL_0JrF8ec2Q5uXtoUT3uotdwJRWOjRAb0QHarD',
            'client-session-id': '079e64c94a114adf',
            'client-version': '7f8e8ffc-0924-405b-b2a6-28f0c305c7af',
            'content-type': 'text/plain;charset=UTF-8',
            'origin': 'https://www.twitch.tv',
            'priority': 'u=1, i',
            'referer': 'https://www.twitch.tv/',
            'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Brave";v="138"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'sec-gpc': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'x-device-id': '1186880d7dab18d4'
        }
        
        print(f"Making GQL request to get VODs")
        response = requests.post(gql_url, json=gql_payload, headers=gql_headers)
        print(f"GQL response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"GQL response text: {response.text[:200]}...")
            return jsonify({'success': False, 'error': 'Failed to get VODs from GQL'}), 500
        
        data = response.json()
        videos_data = data[0].get('data', {}).get('user', {}).get('videos', {}).get('edges', [])
        
        print(f"Raw videos data count: {len(videos_data)}")
        if videos_data:
            print(f"First video title: {videos_data[0].get('node', {}).get('title', 'No title')}")
            print(f"First video published: {videos_data[0].get('node', {}).get('publishedAt', 'No date')}")
        
        videos = []
        for edge in videos_data:
            node = edge.get('node', {})
            
            # Extract M3U8 path from animated preview URL (like the extension does)
            animated_preview_url = node.get('animatedPreviewURL', '')
            preview_thumbnail_url = node.get('previewThumbnailURL', '')
            
            # Try animated preview URL first, then fallback to preview thumbnail URL (like extension)
            m3u8_path_match = re.search(r'(\w+\.cloudfront\.net\/\w{20}_\w+_\d+_\d+)(?=\/)', animated_preview_url)
            if not m3u8_path_match:
                m3u8_path_match = re.search(r'(\w+\.cloudfront\.net\/\w{20}_\w+_\d+_\d+)(?=\/)', preview_thumbnail_url)
            
            if m3u8_path_match:
                m3u8_path = m3u8_path_match.group(1)
                # Extract tokens from the path (like extension)
                tokens_match = re.search(r'(\w{20})_([_\w]+)_(\d+)_(\d+)', m3u8_path)
                if tokens_match:
                    hash_token, channel, stream_id, timestamp = tokens_match.groups()
                    source_url = f"https://{m3u8_path}/chunked/index-dvr.m3u8"
                    
                    # Get server name (like extension)
                    server_match = re.search(r'(\w+)(?=\.cloudfront\.net\/\w{20}_[_\w]+_\d+_\d+\/)', animated_preview_url)
                    m3u8_server = server_match.group(1) if server_match else None
                    
                    video = {
                        'id': node.get('id'),
                        'title': node.get('title', ''),
                        'duration': node.get('lengthSeconds', 0),
                        'created_at': node.get('publishedAt'),
                        'view_count': node.get('viewCount', 0),
                        'preview_url': preview_thumbnail_url,
                        'animated_preview_url': animated_preview_url,
                        'source_url': source_url,
                        'm3u8_path': m3u8_path,
                        'stream_id': stream_id,
                        'timestamp': int(timestamp) * 1000 if timestamp else None,
                        'm3u8_server': m3u8_server,
                        'hash': hash_token,
                        'is_hidden': True  # These are the "hidden" VODs
                    }
                    videos.append(video)
        
        print(f"Found {len(videos)} VODs (including hidden ones)")
        return jsonify({
            'success': True,
            'videos': videos
        })
    except Exception as e:
        print(f"Error in get_channel_videos: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_vod_bp.route('/stream-proxy-m3u8')
def proxy_m3u8():
    """Proxy M3U8 files to bypass CORS restrictions"""
    try:
        m3u8_url = request.args.get('url')
        if not m3u8_url:
            return jsonify({'error': 'Missing url parameter'}), 400
            
        # Validate that it's a CloudFront URL
        if 'cloudfront.net' not in m3u8_url:
            return jsonify({'error': 'Invalid URL'}), 400
            
        print(f"Proxying M3U8: {m3u8_url}")
        
        # Fetch the M3U8 with headers that mimic the extension
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'application/vnd.apple.mpegurl, application/x-mpegurl, application/json, text/plain',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://www.twitch.tv',
            'Referer': 'https://www.twitch.tv/'
        }
        
        response = requests.get(m3u8_url, headers=headers)
        response.raise_for_status()
        
        # Parse and modify M3U8 content to use absolute URLs
        m3u8_content = response.text
        
        # Extract base URL from the M3U8 URL (everything except the filename)
        base_url = m3u8_url.rsplit('/', 1)[0] + '/'
        print(f"M3U8 base URL: {base_url}")
        
        # Replace .ts URLs with proxied URLs to bypass CORS for segments too
        import re
        from urllib.parse import quote
        
        def replace_ts_url(match):
            ts_filename = match.group(1)
            original_ts_url = base_url + ts_filename
            # Create proxied URL for the .ts segment - force HTTPS to avoid Mixed Content
            base_proxy_url = request.url_root.replace('http://', 'https://')
            proxied_ts_url = f"{base_proxy_url}api/twitch/proxy-segment?url={quote(original_ts_url)}"
            return proxied_ts_url
            
        modified_content = re.sub(
            r'^(?!#)([^/\n]+\.ts)$',  # Match lines that are just filename.ts
            replace_ts_url,
            m3u8_content,
            flags=re.MULTILINE
        )
        
        print(f"Modified {len(re.findall(r'\.ts', modified_content))} .ts references in M3U8")
        
        # Debug: Show first few lines of modified content
        lines = modified_content.split('\n')[:10]
        print("First 10 lines of modified M3U8:")
        for i, line in enumerate(lines):
            print(f"  {i+1}: {line}")
        
        # Create Flask response with CORS headers
        from flask import Response
        flask_response = Response(
            modified_content,
            mimetype='application/vnd.apple.mpegurl',
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET',
                'Access-Control-Allow-Headers': 'Content-Type, Range',
                'Access-Control-Expose-Headers': 'Content-Length, Content-Range',
                'Cache-Control': 'no-cache'
            }
        )
        
        return flask_response
        
    except Exception as e:
        print(f"Error proxying M3U8: {str(e)}")
        return jsonify({'error': str(e)}), 500

@twitch_vod_bp.route('/twitch/proxy-segment')
def proxy_segment():
    """Proxy .ts video segments to bypass CORS restrictions"""
    try:
        segment_url = request.args.get('url')
        if not segment_url:
            print("ERROR: Missing url parameter in segment proxy")
            return jsonify({'error': 'Missing url parameter'}), 400
            
        # Validate that it's a CloudFront .ts URL
        if 'cloudfront.net' not in segment_url or not segment_url.endswith('.ts'):
            print(f"ERROR: Invalid segment URL: {segment_url}")
            return jsonify({'error': 'Invalid segment URL'}), 400
            
        print(f"SUCCESS: Proxying segment: {segment_url}")
        
        # Fetch the .ts segment with headers that mimic the extension
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://www.twitch.tv',
            'Referer': 'https://www.twitch.tv/'
        }
        
        response = requests.get(segment_url, headers=headers, stream=True, timeout=30)
        print(f"Segment response status: {response.status_code}")
        print(f"Segment response headers: {dict(response.headers)}")
        response.raise_for_status()
        
        # Create Flask response with CORS headers for video segments
        from flask import Response
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        
        flask_response = Response(
            generate(),
            mimetype='video/MP2T',  # MPEG Transport Stream
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET',
                'Access-Control-Allow-Headers': 'Content-Type, Range',
                'Accept-Ranges': 'bytes',
                'Cache-Control': 'public, max-age=3600'  # Cache segments for 1 hour
            }
        )
        
        if 'content-length' in response.headers:
            flask_response.headers['Content-Length'] = response.headers['content-length']
            
        return flask_response
        
    except Exception as e:
        print(f"Error proxying segment: {str(e)}")
        return jsonify({'error': str(e)}), 500

@twitch_vod_bp.route('/twitch/test-m3u8-reconstruction/<channel_login>/<stream_id>/<int:timestamp>', methods=['GET'])
def test_m3u8_reconstruction(channel_login, stream_id, timestamp):
    """Test M3U8 URL reconstruction for a specific stream"""
    try:
        print(f"Testing M3U8 reconstruction for: {channel_login}_{stream_id}_{timestamp}")
        m3u8_data = find_working_m3u8_url(channel_login, stream_id, timestamp)
        
        if m3u8_data:
            return jsonify({
                'success': True,
                'found_m3u8': True,
                'm3u8_data': m3u8_data,
                'test_params': f"{channel_login}_{stream_id}_{timestamp}"
            })
        else:
            return jsonify({
                'success': True,
                'found_m3u8': False,
                'message': 'No working M3U8 URL found',
                'test_params': f"{channel_login}_{stream_id}_{timestamp}"
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@twitch_vod_bp.route('/twitch/test-sully-main/<channel_login>', methods=['GET'])
def test_sully_main_function(channel_login):
    """Test the main SullyGnome function directly"""
    try:
        print(f"Starting SullyGnome test for channel: {channel_login}")
        
        # Inline the logic to debug step by step
        if channel_login.lower() == 'nv_messiah':
            channel_id = '30130953'
            print(f"Using hardcoded channel ID: {channel_id}")
        else:
            return jsonify({'success': False, 'error': 'Only nv_messiah supported'})
        
        # Make API call - get all 85 streams
        api_url = f"https://sullygnome.com/api/tables/channeltables/streams/90/{channel_id}/%20/1/1/desc/0/85"
        print(f"Making request to: {api_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': f'https://sullygnome.com/channel/{channel_login}/30/streams',
            'X-Requested-With': 'XMLHttpRequest',
            'DNT': '1',
            'Connection': 'keep-alive',
        }
        
        api_response = requests.get(api_url, headers=headers, timeout=15)
        print(f"API Response status: {api_response.status_code}")
        
        if api_response.status_code != 200:
            return jsonify({'success': False, 'error': f'API returned {api_response.status_code}'})
        
        # Parse JSON
        api_response.encoding = 'utf-8'
        data = api_response.json()
        raw_data = data.get('data', [])
        print(f"Raw data count: {len(raw_data)}")
        
        # Parse streams
        parsed_streams = []
        for i, stream in enumerate(raw_data):
            print(f"Processing stream {i+1}/{len(raw_data)}")
            start_datetime = stream.get('startDateTime')
            stream_id = str(stream.get('streamId', '')) if stream.get('streamId') else None
            
            print(f"  startDateTime: {start_datetime}")
            print(f"  streamId: {stream_id}")
            
            if start_datetime and stream_id:
                from datetime import datetime
                timestamp = int(datetime.strptime(start_datetime, "%Y-%m-%dT%H:%M:%SZ").timestamp() * 1000)
                
                parsed_stream = {
                    'duration': (stream.get('length', 0) * 60000),
                    'channel_login': stream.get('channelurl', channel_login),
                    'stream_id': stream_id,
                    'timestamp': timestamp,
                    'timestamp_seconds': timestamp // 1000,
                    'title': f"Stream {stream_id}",
                    'startDateTime': start_datetime,
                }
                parsed_streams.append(parsed_stream)
                print(f"  SUCCESS: Added stream {stream_id}")
            else:
                print(f"  SKIPPED: missing data")
        
        print(f"Total parsed streams: {len(parsed_streams)}")
        
        return jsonify({
            'success': True,
            'stream_count': len(parsed_streams),
            'streams': parsed_streams[:3],
            'total_raw': len(raw_data),
            'debug': f"Parsed {len(parsed_streams)} from {len(raw_data)} raw streams"
        })
        
    except Exception as e:
        print(f"Exception in test_sully_main_function: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        })

@twitch_vod_bp.route('/twitch/test-sully/<channel_login>', methods=['GET'])
def test_sully_debug(channel_login):
    """Debug SullyGnome scraping"""
    try:
        # Use hardcoded channel ID for nv_messiah
        if channel_login.lower() == 'nv_messiah':
            channel_id = '30130953'
        else:
            return jsonify({'error': 'Only nv_messiah supported for testing'})
        
        # Get the streams data from API with browser headers
        api_url = f"https://sullygnome.com/api/tables/channeltables/streams/90/{channel_id}/%20/1/1/desc/0/5"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': f'https://sullygnome.com/channel/{channel_login}/30/streams',
            'X-Requested-With': 'XMLHttpRequest'
        }
        # Remove Accept-Encoding to prevent compression issues
        headers_no_compression = headers.copy()
        if 'Accept-Encoding' in headers_no_compression:
            del headers_no_compression['Accept-Encoding']
            
        api_response = requests.get(api_url, headers=headers_no_compression)
        api_response.raise_for_status()
        
        print(f"SullyGnome response status: {api_response.status_code}")
        # Skip printing response text to avoid encoding issues
        # print(f"SullyGnome response text: {api_response.text[:500]}")
        
        try:
            # Fix encoding issue
            api_response.encoding = 'utf-8'
            data = api_response.json()
            raw_streams = data.get('data', [])
            
            return jsonify({
                'success': True,
                'raw_count': len(raw_streams),
                'first_stream': raw_streams[0] if raw_streams else None,
                'api_url': api_url,
                'response_preview': api_response.text[:200]
            })
        except:
            return jsonify({
                'success': False,
                'error': 'JSON parse failed',
                'api_url': api_url,
                'response_text': api_response.text[:500],
                'status_code': api_response.status_code
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def extract_hidden_vods_from_gql(channel_login):
    """Extract hidden VODs for any channel using GraphQL like the extension does"""
    try:
        print(f"Extracting hidden VODs for {channel_login} using GraphQL")
        
        # Get channel info first
        headers = get_twitch_headers()
        user_url = f"https://api.twitch.tv/helix/users?login={channel_login}"
        user_response = requests.get(user_url, headers=headers)
        
        if user_response.status_code != 200:
            print(f"Failed to get user info: {user_response.status_code}")
            return []
            
        user_data = user_response.json().get('data', [])
        if not user_data:
            print(f"User {channel_login} not found")
            return []
            
        channel_id = user_data[0]['id']
        print(f"Found channel ID: {channel_id}")
        
        # Try multiple GraphQL queries to get different types of VODs
        gql_url = "https://gql.twitch.tv/gql"
        
        # Query 1: ARCHIVE broadcasts (what extension uses)
        gql_payload_archive = [
            {
                "operationName": "FilterableVideoTower_Videos",
                "variables": {
                    "limit": 100,
                    "channelOwnerLogin": channel_login,
                    "broadcastType": "ARCHIVE",
                    "videoSort": "TIME"
                },
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "a937f1d22e269e39a03b509f65a7490f9fc247d7f83d6ac1421523e3b68042cb"
                    }
                }
            }
        ]
        
        # Query 2: Try without broadcastType to get all videos
        gql_payload_all = [
            {
                "operationName": "FilterableVideoTower_Videos",
                "variables": {
                    "limit": 100,
                    "channelOwnerLogin": channel_login,
                    "broadcastType": None,
                    "videoSort": "TIME"
                },
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "a937f1d22e269e39a03b509f65a7490f9fc247d7f83d6ac1421523e3b68042cb"
                    }
                }
            }
        ]
        
        # Headers that mimic the browser extension
        gql_headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'client-id': 'kimne78kx3ncx6brgo4mv6wki5h1ko',
            'content-type': 'text/plain;charset=UTF-8',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
        }
        
        # Try both queries and combine results
        all_videos_data = []
        
        # Try ARCHIVE query first
        print("Trying ARCHIVE broadcastType query...")
        response = requests.post(gql_url, json=gql_payload_archive, headers=gql_headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            archive_videos = data[0].get('data', {}).get('user', {}).get('videos', {}).get('edges', [])
            print(f"ARCHIVE query found {len(archive_videos)} videos")
            all_videos_data.extend(archive_videos)
        else:
            print(f"ARCHIVE query failed: {response.status_code}")
        
        # Try broadcastType=None query for more videos
        print("Trying broadcastType=None query...")
        response2 = requests.post(gql_url, json=gql_payload_all, headers=gql_headers, timeout=30)
        if response2.status_code == 200:
            data2 = response2.json()
            all_videos = data2[0].get('data', {}).get('user', {}).get('videos', {}).get('edges', [])
            print(f"All videos query found {len(all_videos)} videos")
            # Add videos that aren't already in our list
            existing_ids = {v.get('node', {}).get('id') for v in all_videos_data}
            for video in all_videos:
                video_id = video.get('node', {}).get('id')
                if video_id not in existing_ids:
                    all_videos_data.append(video)
        else:
            print(f"All videos query failed: {response2.status_code}")
        
        print(f"Total unique videos from all queries: {len(all_videos_data)}")
        videos_data = all_videos_data
        
        hidden_vods = []
        for edge in videos_data:
            video = edge.get('node', {})
            
            # Debug: Show what we're getting from GraphQL with REAL dates
            published_at = video.get('publishedAt', 'Unknown')
            length_seconds = video.get('lengthSeconds', 0)
            
            # Parse the actual date from GraphQL
            real_date = "Unknown"
            if published_at and published_at != 'Unknown':
                try:
                    from datetime import datetime
                    # Parse ISO date format from Twitch
                    dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                    real_date = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
                except:
                    real_date = published_at
            
            print(f"GraphQL Video: '{video.get('title', 'No title')}' - Duration: {length_seconds}s ({length_seconds//3600}h {(length_seconds%3600)//60}m) - REAL DATE: {real_date}")
            
            # Extract M3U8 path from animated preview URL (like the extension)
            animated_preview_url = video.get('animatedPreviewURL', '')
            preview_thumbnail_url = video.get('previewThumbnailURL', '')
            
            print(f"  Animated URL: {animated_preview_url[:100]}..." if animated_preview_url else "  No animated URL")
            print(f"  Preview URL: {preview_thumbnail_url[:100]}..." if preview_thumbnail_url else "  No preview URL")
            
            # Try both URLs to extract CloudFront path
            m3u8_path = None
            for url in [animated_preview_url, preview_thumbnail_url]:
                if url:
                    # Match pattern: domain.cloudfront.net/hash_channel_streamid_timestamp
                    match = re.search(r'(\w+\.cloudfront\.net\/\w{20}_\w+_\d+_\d+)', url)
                    if match:
                        m3u8_path = match.group(1)
                        print(f"  ✅ Found M3U8 path: {m3u8_path}")
                        break
            
            if not m3u8_path:
                print(f"  ❌ No M3U8 path found for this video")
            
            if m3u8_path:
                # Extract components from the path
                path_parts = m3u8_path.split('/')
                if len(path_parts) >= 2:
                    server = path_parts[0].split('.')[0]
                    filename = path_parts[1]
                    parts = filename.split('_')
                    
                    if len(parts) >= 4:
                        hash_token = parts[0]
                        stream_id = parts[2]
                        timestamp = parts[3]
                        
                        # Create hidden VOD entry using extension's timestamp logic
                        published_at = video.get('publishedAt')
                        
                        # Use publishedAt if available, otherwise fall back to timestamp from filename
                        if published_at:
                            try:
                                from datetime import datetime
                                dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                                timestamp_ms = int(dt.timestamp() * 1000)
                            except:
                                timestamp_ms = int(timestamp) * 1000 if timestamp.isdigit() else None
                        else:
                            timestamp_ms = int(timestamp) * 1000 if timestamp.isdigit() else None
                        
                        hidden_vod = {
                            'id': video.get('id'),
                            'stream_id': stream_id,
                            'timestamp': timestamp_ms,
                            'title': video.get('title', 'Hidden VOD'),
                            'duration': video.get('lengthSeconds', 0),
                            'view_count': video.get('viewCount', 0),
                            'created_at': published_at,
                            'preview_url': preview_thumbnail_url,
                            'animated_preview_url': animated_preview_url,
                            'is_hidden': True,
                            'source_url': f"https://{m3u8_path}/chunked/index-dvr.m3u8",
                            'hash': hash_token,
                            'server': server,
                            'm3u8_path': m3u8_path
                        }
                        hidden_vods.append(hidden_vod)
                        # Skip printing title to avoid encoding issues
                        print(f"Extracted hidden VOD: {stream_id}")
        
        print(f"Successfully extracted {len(hidden_vods)} hidden VODs")
        return hidden_vods
        
    except Exception as e:
        print(f"Error extracting hidden VODs: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

@twitch_vod_bp.route('/stream-recent/<channel_login>', methods=['GET'])
def get_recent_streams_with_vods(channel_login):
    """Get recent streams merged with VOD data (works for all channels dynamically)"""
    try:
        print(f"Getting recent streams with VODs for channel: {channel_login}")
        
        # Method 1: Get VODs from Twitch API
        # Deprecated: localhost dependency is removed for Vercel
        api_vods = []
        print("Skipping localhost VOD API; proceeding with GQL + SullyGnome only")
        
        # Method 2: Extract hidden VODs using GraphQL (works for all channels)  
        hidden_vods = extract_hidden_vods_from_gql(channel_login)
        print(f"Hidden VODs: {len(hidden_vods)} videos")
        
        # Method 2.5: Get individual stream data from SullyGnome (THIS IS KEY!)
        print("Getting individual stream data from SullyGnome...")
        sully_streams = get_sully_streams_data(channel_login)
        print(f"SullyGnome streams: {len(sully_streams)} individual streams")
        
        # Method 3: Merge SullyGnome streams with VODs (like extension does)
        print("Merging SullyGnome individual streams with Twitch VODs...")
        merged_streams = merge_vods_with_sully_gnome(sully_streams, hidden_vods + api_vods)
        print(f"Merged result: {len(merged_streams)} total streams")
        
        # FILTER: Only show streams that exist in SullyGnome (true hidden/deleted VODs)
        # Remove any public VODs that aren't in SullyGnome's database
        sully_stream_ids = {str(s.get('stream_id')) for s in sully_streams if s.get('stream_id')}
        print(f"SullyGnome stream IDs: {len(sully_stream_ids)} streams")
        
        filtered_streams = []
        for stream in merged_streams:
            stream_id = str(stream.get('stream_id', ''))
            if stream_id in sully_stream_ids:
                # This stream exists in SullyGnome database - it's a true hidden/deleted VOD
                filtered_streams.append(stream)
                print(f"KEEP: SullyGnome stream: {stream_id}")
            else:
                # This is a public VOD not in SullyGnome - filter it out
                print(f"FILTER: public VOD: {stream_id}")
        
        print(f"Filtered to {len(filtered_streams)} SullyGnome streams (removed {len(merged_streams) - len(filtered_streams)} public VODs)")
        all_vods = filtered_streams
        
        # No more fake data - only use real GraphQL extracted VODs
        
        # Remove duplicates by stream_id and sort by timestamp (newest first)
        # BUT include all VODs, even those without stream_id (like the extension does)
        seen_stream_ids = set()
        seen_vod_ids = set()
        unique_vods = []
        for vod in sorted(all_vods, key=lambda x: x.get('timestamp', 0), reverse=True):
            stream_id = vod.get('stream_id')
            vod_id = vod.get('id')
            
            # Use multiple keys to deduplicate: stream_id, vod_id, or combination of title+timestamp
            should_include = True
            
            if stream_id and stream_id in seen_stream_ids:
                should_include = False
            elif vod_id and vod_id in seen_vod_ids:
                should_include = False
            
            if should_include:
                if stream_id:
                    seen_stream_ids.add(stream_id)
                if vod_id:
                    seen_vod_ids.add(vod_id)
                    
                # Mark any VOD with a source_url (M3U8) as hidden
                if vod.get('source_url'):
                    vod['is_hidden'] = True
                unique_vods.append(vod)
        
        # Show ALL streams without any date filtering (like the extension does)
        recent_vods = unique_vods
        
        print(f"Total unique streams found: {len(recent_vods)}")
        
        # Debug: Show first 15 streams
        print("First 15 streams found:")
        for i, vod in enumerate(recent_vods[:15]):  # Show first 15
            vod_time = vod.get('timestamp', 0)
            if vod_time:
                from datetime import datetime
                try:
                    dt = datetime.fromtimestamp(vod_time / 1000)
                    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    date_str = f"Invalid timestamp: {vod_time}"
            else:
                date_str = "No timestamp"
            
            duration_h = vod.get('duration', 0) // 3600
            duration_m = (vod.get('duration', 0) % 3600) // 60
            print(f"  {i+1}. '{vod.get('title', 'No title')[:50]}...' - {duration_h}h {duration_m}m - {date_str} - Hidden: {vod.get('is_hidden', False)}")
        
        print(f"Final result: {len(recent_vods)} SullyGnome streams (hidden/deleted VODs only)")
        with_m3u8_count = len([v for v in recent_vods if v.get('source_url')])
        without_m3u8_count = len([v for v in recent_vods if not v.get('source_url')])
        print(f"  - {with_m3u8_count} streams with working M3U8 URLs")
        print(f"  - {without_m3u8_count} streams without M3U8 URLs")
        
        return jsonify({
            'success': True,
            'streams': recent_vods,
            'streams_with_m3u8': with_m3u8_count,
            'streams_without_m3u8': without_m3u8_count,
            'total_sully_streams': len(recent_vods),
            'note': 'Only showing SullyGnome streams (hidden/deleted VODs), no public VODs'
        })
        
    except Exception as e:
        print(f"Error in get_recent_streams_with_vods: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

def get_channel_videos_with_tokens_internal(channel_login):
    """Internal function to get VODs without HTTP context"""
    try:
        print(f"Getting VODs for channel: {channel_login} (internal)")
        
        # Use GQL to get VODs (including hidden ones)
        gql_url = "https://gql.twitch.tv/gql"
        gql_payload = [{
            "operationName": "FilterableVideoTower_Videos",
            "variables": {
                "limit": 200,
                "channelOwnerLogin": channel_login,
                "broadcastType": "ARCHIVE",
                "videoSort": "TIME"
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "a937f1d22e269e39a03b509f65a7490f9fc247d7f83d6ac1421523e3b68042cb"
                }
            }
        }]
        
        # GQL headers
        gql_headers = {
            'accept': '*/*',
            'accept-language': 'en-US',
            'client-id': 'kimne78kx3ncx6brgo4mv6wki5h1ko',
            'content-type': 'text/plain;charset=UTF-8',
            'origin': 'https://www.twitch.tv',
            'referer': 'https://www.twitch.tv/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'x-device-id': '1186880d7dab18d4'
        }
        
        response = requests.post(gql_url, json=gql_payload, headers=gql_headers)
        
        if response.status_code != 200:
            print(f"GQL response text: {response.text[:500]}...")
            return {'success': False, 'error': f'Failed to get VODs from GQL: {response.status_code}'}
        
        data = response.json()
        videos_data = data[0].get('data', {}).get('user', {}).get('videos', {}).get('edges', [])
        
        videos = []
        for edge in videos_data:
            node = edge.get('node', {})
            
            # Extract M3U8 path from animated preview URL (like the extension does)
            animated_preview_url = node.get('animatedPreviewURL', '')
            preview_thumbnail_url = node.get('previewThumbnailURL', '')
            
            # Try animated preview URL first, then fallback to preview thumbnail URL (like extension)
            m3u8_path_match = re.search(r'(\w+\.cloudfront\.net\/\w{20}_\w+_\d+_\d+)(?=\/)', animated_preview_url)
            if not m3u8_path_match:
                m3u8_path_match = re.search(r'(\w+\.cloudfront\.net\/\w{20}_\w+_\d+_\d+)(?=\/)', preview_thumbnail_url)
            
            if m3u8_path_match:
                m3u8_path = m3u8_path_match.group(1)
                # Extract tokens from the path (like extension)
                tokens_match = re.search(r'(\w{20})_([_\w]+)_(\d+)_(\d+)', m3u8_path)
                if tokens_match:
                    hash_token, channel, stream_id, timestamp = tokens_match.groups()
                    source_url = f"https://{m3u8_path}/chunked/index-dvr.m3u8"
                    
                    # Get server name (like extension)
                    server_match = re.search(r'(\w+)(?=\.cloudfront\.net\/\w{20}_[_\w]+_\d+_\d+\/)', animated_preview_url)
                    m3u8_server = server_match.group(1) if server_match else None
                    
                    video = {
                        'id': node.get('id'),
                        'title': node.get('title', ''),
                        'duration': node.get('lengthSeconds', 0),
                        'created_at': node.get('publishedAt'),
                        'view_count': node.get('viewCount', 0),
                        'preview_url': preview_thumbnail_url,
                        'animated_preview_url': animated_preview_url,
                        'source_url': source_url,
                        'm3u8_path': m3u8_path,
                        'stream_id': stream_id,
                        'timestamp': int(timestamp) * 1000 if timestamp else None,
                        'm3u8_server': m3u8_server,
                        'hash': hash_token,
                        'is_hidden': True
                    }
                    videos.append(video)
        
        return {'success': True, 'videos': videos}
        
    except Exception as e:
        print(f"Error in get_channel_videos_with_tokens_internal: {str(e)}")
        return {'success': False, 'error': str(e)}

@twitch_vod_bp.route('/twitch/videos-with-tokens/<channel_login>', methods=['GET', 'POST'])
def get_channel_videos_with_tokens(channel_login):
    """Get channel videos/VODs using tokens from frontend (like extension)"""
    try:
        print(f"Getting VODs for channel: {channel_login} with tokens")
        
        # Handle both GET and POST requests
        if request.method == 'POST':
            # Get tokens from request body (sent from frontend)  
            data = request.get_json() or {}
            tokens = data.get('tokens', {})
        else:
            # For GET requests, use default tokens
            tokens = {}
        
        # If no tokens provided, try without auth (may get limited results)
        if not tokens:
            print("No tokens provided, trying without authentication")
            tokens = {
                'client_id': 'kimne78kx3ncx6brgo4mv6wki5h1ko',
                'device_id': '1186880d7dab18d4'
            }
        
        print(f"Received tokens: {list(tokens.keys())}")
        print(f"Target channel: {channel_login}")
        
        # Use GQL to get VODs (including hidden ones)
        gql_url = "https://gql.twitch.tv/gql"
        gql_payload = [{
            "operationName": "FilterableVideoTower_Videos",
            "variables": {
                "limit": 100,  # Reasonable limit to avoid blocks
                "channelOwnerLogin": channel_login,
                "broadcastType": "ARCHIVE",
                "videoSort": "TIME"
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "a937f1d22e269e39a03b509f65a7490f9fc247d7f83d6ac1421523e3b68042cb"
                }
            }
        }]
        
        # GQL headers (working version)
        gql_headers = {
            'accept': '*/*',
            'accept-language': 'en-US',
            'client-id': 'kimne78kx3ncx6brgo4mv6wki5h1ko',
            'content-type': 'text/plain;charset=UTF-8',
            'origin': 'https://www.twitch.tv',
            'referer': 'https://www.twitch.tv/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'x-device-id': '1186880d7dab18d4'
        }
        
        # Add client-integrity token if available
        if tokens.get('client_integrity'):
            gql_headers['client-integrity'] = tokens['client_integrity']
            print(f"Using client-integrity token: {tokens['client_integrity'][:50]}...")
        
        # Add authorization if available
        if tokens.get('oauth') and tokens['oauth'].startswith('OAuth '):
            gql_headers['authorization'] = tokens['oauth']
            print(f"Using OAuth authorization: {tokens['oauth'][:20]}...")
        elif tokens.get('authorization') and tokens['authorization'].startswith('OAuth '):
            gql_headers['authorization'] = tokens['authorization']
            print(f"Using OAuth authorization: {tokens['authorization'][:20]}...")
        else:
            print("No valid OAuth token found, proceeding without authorization")
        
        print(f"Making GQL request to get VODs with tokens")
        print(f"GQL URL: {gql_url}")
        print(f"GQL Headers: {gql_headers}")
        print(f"GQL Payload: {gql_payload}")
        
        try:
            response = requests.post(gql_url, json=gql_payload, headers=gql_headers)
            print(f"GQL response status: {response.status_code}")
            print(f"GQL response headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                print(f"GQL response text: {response.text[:500]}...")
                return jsonify({'success': False, 'error': f'Failed to get VODs from GQL: {response.status_code}'}), 500
        except Exception as e:
            print(f"Exception during GQL request: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': f'GQL request failed: {str(e)}'}), 500
        
        try:
            data = response.json()
            print(f"GQL response data keys: {list(data[0].keys()) if data and len(data) > 0 else 'No data'}")
            videos_data = data[0].get('data', {}).get('user', {}).get('videos', {}).get('edges', [])
        except Exception as e:
            print(f"Exception parsing GQL response: {str(e)}")
            print(f"Response text: {response.text[:500]}...")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': f'Failed to parse GQL response: {str(e)}'}), 500
        
        print(f"Raw videos data count: {len(videos_data)}")
        if videos_data:
            print(f"First video title: {videos_data[0].get('node', {}).get('title', 'No title')}")
            print(f"First video published: {videos_data[0].get('node', {}).get('publishedAt', 'No date')}")
        
        videos = []
        for edge in videos_data:
            node = edge.get('node', {})
            
            # Extract M3U8 path from animated preview URL (like the extension does)
            animated_preview_url = node.get('animatedPreviewURL', '')
            preview_thumbnail_url = node.get('previewThumbnailURL', '')
            
            # Try animated preview URL first, then fallback to preview thumbnail URL (like extension)
            m3u8_path_match = re.search(r'(\w+\.cloudfront\.net\/\w{20}_\w+_\d+_\d+)(?=\/)', animated_preview_url)
            if not m3u8_path_match:
                m3u8_path_match = re.search(r'(\w+\.cloudfront\.net\/\w{20}_\w+_\d+_\d+)(?=\/)', preview_thumbnail_url)
            
            if m3u8_path_match:
                m3u8_path = m3u8_path_match.group(1)
                # Extract tokens from the path (like extension)
                tokens_match = re.search(r'(\w{20})_([_\w]+)_(\d+)_(\d+)', m3u8_path)
                if tokens_match:
                    hash_token, channel, stream_id, timestamp = tokens_match.groups()
                    source_url = f"https://{m3u8_path}/chunked/index-dvr.m3u8"
                    
                    # Get server name (like extension)
                    server_match = re.search(r'(\w+)(?=\.cloudfront\.net\/\w{20}_[_\w]+_\d+_\d+\/)', animated_preview_url)
                    m3u8_server = server_match.group(1) if server_match else None
                    
                    video = {
                        'id': node.get('id'),
                        'title': node.get('title', ''),
                        'duration': node.get('lengthSeconds', 0),
                        'created_at': node.get('publishedAt'),
                        'view_count': node.get('viewCount', 0),
                        'preview_url': preview_thumbnail_url,
                        'animated_preview_url': animated_preview_url,
                        'source_url': source_url,
                        'm3u8_path': m3u8_path,
                        'stream_id': stream_id,
                        'timestamp': int(timestamp) * 1000 if timestamp else None,
                        'm3u8_server': m3u8_server,
                        'hash': hash_token,
                        'is_hidden': True  # These are the "hidden" VODs
                    }
                    videos.append(video)
        
        print(f"Found {len(videos)} VODs (including hidden ones)")
        return jsonify({
            'success': True,
            'videos': videos
        })
    except Exception as e:
        print(f"Error in get_channel_videos_with_tokens: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_vod_bp.route('/stream-video/<video_id>', methods=['GET'])
def get_video_info(video_id):
    """Get video information and available qualities"""
    try:
        print(f"Getting video info for video_id: {video_id}")
        
        # For hidden VODs, we need to get the channel info first to reconstruct the video
        # Let's try a different approach - get the video info from the channel's VOD list
        # This is a simplified approach - in a real implementation, you'd cache the VOD data
        
        # For now, let's try to get the video info using a different GQL query
        gql_url = "https://gql.twitch.tv/gql"
        gql_payload = [{
            "operationName": "VideoPlayer_Video",
            "variables": {
                "videoID": video_id
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "8e8b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b"
                }
            }
        }]
        
        gql_headers = {
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'en-US',
            'client-id': 'kimne78kx3ncx6brgo4mv6wki5h1ko',
            'client-integrity': 'v4.local.EOvZGU3SI2Z3hQOEHt4NJvAW7hnpgb6RTghw6yw3K0PeQbs_sCoNV8gKG5T5Jd-xD5HRHF41chxNRh84-5KllcgxU46HzZxPtKye386WQVFVIjmTBrauqq5fEHZmok7O9kXMQvMhRDYTaEVuXK2rdwCo-lGT4K6wPEMxDU6TF0PCPXnaWy2R8xdvqZ5kdGLKRDvyaszTVxpr8wlFiL6Q5VKAQyIDXUYvfuyAx2Pcs3KDryMIwn2UsSbMAxTWVPgtbRad-3QynJ3tnDfs9LaQnteHeDueWg0mMPPqyCGoXIN7BAVcfMhqt9hdPsOuo2YNKOxN2FWx0AOWXe487zR56I3ge1lu00OfDY5JdRXCvXciqZ2ozQxNqDmuVwKj4wV-MVZGTYL_0JrF8ec2Q5uXtoUT3uotdwJRWOjRAb0QHarD',
            'client-session-id': '079e64c94a114adf',
            'client-version': '7f8e8ffc-0924-405b-b2a6-28f0c305c7af',
            'content-type': 'text/plain;charset=UTF-8',
            'origin': 'https://www.twitch.tv',
            'priority': 'u=1, i',
            'referer': 'https://www.twitch.tv/',
            'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Brave";v="138"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'sec-gpc': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
        }
        
        print(f"Getting video player info from GQL")
        response = requests.post(gql_url, json=gql_payload, headers=gql_headers)
        print(f"GQL response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"GQL response text: {response.text[:200]}...")
            # Try a simpler approach - construct the URL directly
            return get_video_info_direct(video_id)
        
        data = response.json()
        video_data = data[0].get('data', {}).get('video', {})
        
        if not video_data:
            print("Video not found in GQL, trying direct approach")
            return get_video_info_direct(video_id)
        
        # Extract the direct M3U8 URL from the animated preview
        animated_preview_url = video_data.get('animatedPreviewURL', '')
        m3u8_path_match = re.search(r'(\w+\.cloudfront\.net\/\w{20}_\w+_\d+_\d+)(?=\/)', animated_preview_url)
        
        if not m3u8_path_match:
            print("Could not extract M3U8 path, trying direct approach")
            return get_video_info_direct(video_id)
        
        m3u8_path = m3u8_path_match.group(1)
        playlist_url = f"https://{m3u8_path}/chunked/index-dvr.m3u8"
        
        print(f"Direct playlist URL: {playlist_url}")
        
        # Get the playlist to extract qualities
        playlist_response = requests.get(playlist_url)
        print(f"Playlist response status: {playlist_response.status_code}")
        
        if playlist_response.status_code != 200:
            print(f"Playlist response text: {playlist_response.text[:200]}...")
            return jsonify({'success': False, 'error': 'Failed to get playlist'}), 500
        
        # Parse playlist to get available qualities
        playlist_content = playlist_response.text
        print(f"Playlist content length: {len(playlist_content)}")
        qualities = []
        
        # Extract quality information from playlist
        lines = playlist_content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('#EXT-X-STREAM-INF:'):
                # Extract resolution from the next line (URL)
                if i + 1 < len(lines) and not lines[i + 1].startswith('#'):
                    quality_info = line
                    resolution_match = re.search(r'RESOLUTION=(\d+x\d+)', quality_info)
                    bandwidth_match = re.search(r'BANDWIDTH=(\d+)', quality_info)
                    
                    if resolution_match:
                        resolution = resolution_match.group(1)
                        bandwidth = bandwidth_match.group(1) if bandwidth_match else 'Unknown'
                        qualities.append({
                            'resolution': resolution,
                            'bandwidth': bandwidth,
                            'url': lines[i + 1]
                        })
        
        print(f"Found {len(qualities)} quality options")
        
        # Create video object similar to the extension
        video = {
            'id': video_id,
            'title': video_data.get('title', ''),
            'description': video_data.get('description', ''),
            'duration': video_data.get('lengthSeconds', 0),
            'created_at': video_data.get('publishedAt'),
            'view_count': video_data.get('viewCount', 0),
            'preview_url': video_data.get('previewThumbnailURL'),
            'animated_preview_url': animated_preview_url
        }
        
        return jsonify({
            'success': True,
            'video': video,
            'qualities': qualities,
            'playlist_url': playlist_url
        })
    except Exception as e:
        print(f"Error in get_video_info: {str(e)}")
        import traceback
        traceback.print_exc()
        return get_video_info_direct(video_id)

def get_video_info_direct(video_id):
    """Fallback method to get video info using direct URL construction"""
    try:
        print(f"Using direct method for video_id: {video_id}")
        
        # For now, let's try to construct a basic video object
        # In a real implementation, you'd store the video info from the VODs list
        video = {
            'id': video_id,
            'title': f'VOD {video_id}',
            'description': 'Video information not available',
            'duration': 0,
            'created_at': None,
            'view_count': 0,
            'preview_url': None,
            'animated_preview_url': None
        }
        
        # Try to get qualities from a basic playlist
        # This is a simplified approach - you'd need the actual M3U8 URL
        qualities = []
        
        return jsonify({
            'success': True,
            'video': video,
            'qualities': qualities,
            'playlist_url': None
        })
    except Exception as e:
        print(f"Error in get_video_info_direct: {str(e)}")
        return jsonify({'success': False, 'error': 'Video not found'}), 404

@twitch_vod_bp.route('/stream-live/<channel_login>', methods=['GET'])
def get_live_stream(channel_login):
    """Get live stream information"""
    try:
        headers = get_twitch_headers()
        
        # Get user ID
        user_url = f"https://api.twitch.tv/helix/users?login={channel_login}"
        user_response = requests.get(user_url, headers=headers)
        user_response.raise_for_status()
        
        user_data = user_response.json().get('data', [])
        if not user_data:
            return jsonify({'success': False, 'error': 'Channel not found'}), 404
        
        user_id = user_data[0]['id']
        
        # Get stream info
        stream_url = f"https://api.twitch.tv/helix/streams?user_id={user_id}"
        stream_response = requests.get(stream_url, headers=headers)
        stream_response.raise_for_status()
        
        stream_data = stream_response.json().get('data', [])
        if not stream_data:
            return jsonify({
                'success': True,
                'live': False,
                'message': 'Channel is not live'
            })
        
        stream = stream_data[0]
        
        # Get playback access token for live stream
        token_url = "https://gql.twitch.tv/gql"
        token_payload = {
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
        
        # Use GQL headers (matching the extension exactly)
        gql_headers = {
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'en-US',
            'client-id': 'kimne78kx3ncx6brgo4mv6wki5h1ko',
            'client-integrity': 'v4.local.EOvZGU3SI2Z3hQOEHt4NJvAW7hnpgb6RTghw6yw3K0PeQbs_sCoNV8gKG5T5Jd-xD5HRHF41chxNRh84-5KllcgxU46HzZxPtKye386WQVFVIjmTBrauqq5fEHZmok7O9kXMQvMhRDYTaEVuXK2rdwCo-lGT4K6wPEMxDU6TF0PCPXnaWy2R8xdvqZ5kdGLKRDvyaszTVxpr8wlFiL6Q5VKAQyIDXUYvfuyAx2Pcs3KDryMIwn2UsSbMAxTWVPgtbRad-3QynJ3tnDfs9LaQnteHeDueWg0mMPPqyCGoXIN7BAVcfMhqt9hdPsOuo2YNKOxN2FWx0AOWXe487zR56I3ge1lu00OfDY5JdRXCvXciqZ2ozQxNqDmuVwKj4wV-MVZGTYL_0JrF8ec2Q5uXtoUT3uotdwJRWOjRAb0QHarD',
            'client-session-id': '079e64c94a114adf',
            'client-version': '7f8e8ffc-0924-405b-b2a6-28f0c305c7af',
            'content-type': 'text/plain;charset=UTF-8',
            'origin': 'https://www.twitch.tv',
            'priority': 'u=1, i',
            'referer': 'https://www.twitch.tv/',
            'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Brave";v="138"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'sec-gpc': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'x-device-id': '1186880d7dab18d4'
        }
        
        token_response = requests.post(token_url, json=token_payload, headers=gql_headers)
        token_response.raise_for_status()
        token_data = token_response.json()
        
        access_token = token_data['data']['streamPlaybackAccessToken']
        
        # Get playlist URL
        playlist_url = f"https://usher.ttvnw.net/api/channel/hls/{channel_login}.m3u8?client_id={TWITCH_CLIENT_ID}&token={access_token['value']}&sig={access_token['signature']}&allow_source=true&allow_audio_only=false"
        
        return jsonify({
            'success': True,
            'live': True,
            'stream': stream,
            'playlist_url': playlist_url
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_vod_bp.route('/stream-clip/<clip_slug>', methods=['GET'])
def get_clip_info(clip_slug):
    """Get clip information"""
    try:
        headers = get_twitch_headers()
        
        # Get clip info
        clip_url = f"https://api.twitch.tv/helix/clips?id={clip_slug}"
        clip_response = requests.get(clip_url, headers=headers)
        clip_response.raise_for_status()
        
        clip_data = clip_response.json().get('data', [])
        if not clip_data:
            return jsonify({'success': False, 'error': 'Clip not found'}), 404
        
        clip = clip_data[0]
        
        # Get clip download URL
        download_url = clip['thumbnail_url'].replace('-preview-480x272.jpg', '.mp4')
        
        return jsonify({
            'success': True,
            'clip': clip,
            'download_url': download_url
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_vod_bp.route('/twitch/download', methods=['POST'])
def download_video():
    """Download video segment"""
    try:
        data = request.get_json()
        url = data.get('url')
        filename = data.get('filename', 'video.ts')
        
        if not url:
            return jsonify({'success': False, 'error': 'URL is required'}), 400
        
        # Download the video segment
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Return the video data
        return response.content, 200, {
            'Content-Type': 'video/mp2t',
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500 
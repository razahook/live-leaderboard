import requests
import json
import time
import re
from flask import Blueprint, jsonify, request

twitch_hidden_vods_bp = Blueprint('twitch_hidden_vods', __name__)

@twitch_hidden_vods_bp.route('/api/twitch/hidden-vods/<channel_login>', methods=['POST'])
def get_hidden_vods(channel_login):
    """Get hidden VODs exactly like the extension does - this is the main functionality"""
    try:
        print(f"\n🔍 Getting HIDDEN VODs for channel: {channel_login}")
        
        # Get tokens from request body (sent from frontend JS)
        data = request.get_json() or {}
        tokens = data.get('tokens', {})
        
        print(f"📋 Received tokens: {list(tokens.keys())}")
        
        # Use exact GQL query from extension (background.js:484-486)
        gql_url = "https://gql.twitch.tv/gql"
        gql_payload = [{
            "operationName": "FilterableVideoTower_Videos",
            "variables": {
                "limit": 75,  # Extension uses 75
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
        
        # Use your exact browser headers
        gql_headers = {
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'en-US',
            'authorization': 'OAuth 776n9yzyvxcdul878r2lszi7b7ma6q',
            'client-id': 'kimne78kx3ncx6brgo4mv6wki5h1ko',
            'client-integrity': 'v4.local.z66uf8j7GlaxRR4E6IbYuygPn2PuvIh6q_k1MoSlF5Rxjf8B6WOrBGuru7co4NTet0tUu0V1Yz_hXZ9WWXgmgH825_ARiFnVl7VeaiiqKRW5ulknTpDOK6N9nEYzdJJcj8BnjcygMosDepP-jjePfhpLfqGohvpZalVMkMEJCZ4XE0bz2isd014nCGdfDvNniEyxL3_x0ERCnlsnU_LWhsjobr3FGbMnZG_fXTDkXojKOq_bN64i6x-DNAyKNK-0Gcl6qBGnvY7H7FqY7io0SilyNgYLVNEHr5W3bdUZUkF_RHH_LCYvrcQyJEGrZooJXJ_ShZgqwy2nMrd4WgeJK_N5pFuXqDNlKjdP3DVacgJ0UQMHfK_IkE0tnvlU-eDfrNF3raM3vVJn2msM6_vcaboILOlOsCcmBG14F65hFl5dEtlKcy8aKmnWLg',
            'client-session-id': 'cc626a72e83b849a',
            'client-version': 'd6904cb5-d7fe-431a-832b-e19eab1fa585',
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
        
        # Override with any tokens passed from frontend (for future token rotation)
        if tokens.get('authorization'):
            gql_headers['authorization'] = tokens['authorization']
            print(f"✅ Using custom authorization token")
        if tokens.get('client_integrity'):
            gql_headers['client-integrity'] = tokens['client_integrity']
            print(f"✅ Using custom client-integrity token")
        if tokens.get('device_id'):
            gql_headers['x-device-id'] = tokens['device_id']
            print(f"✅ Using custom device-id")
            
        print(f"✅ Using hardcoded browser headers that match your session")
        
        print(f"🌐 Making GQL request to: {gql_url}")
        
        try:
            response = requests.post(gql_url, json=gql_payload, headers=gql_headers, timeout=10)
            print(f"📊 GQL response status: {response.status_code}")
            
            if response.status_code == 401:
                return jsonify({
                    'success': False, 
                    'error': 'Authentication failed - need valid Twitch tokens',
                    'hint': 'Make sure you are logged into Twitch and pass proper tokens'
                }), 401
                
            if response.status_code != 200:
                print(f"❌ GQL Error Response: {response.text[:500]}...")
                return jsonify({
                    'success': False, 
                    'error': f'GQL request failed with status {response.status_code}',
                    'response_text': response.text[:200]
                }), 500
                
        except Exception as e:
            print(f"❌ Request Exception: {str(e)}")
            return jsonify({'success': False, 'error': f'Request failed: {str(e)}'}), 500
        
        # Parse response
        try:
            data = response.json()
            if not data or len(data) == 0:
                print("❌ Empty response data")
                return jsonify({'success': False, 'error': 'Empty response from Twitch'}), 500
                
            videos_data = data[0].get('data', {}).get('user', {}).get('videos', {}).get('edges', [])
            print(f"📺 Found {len(videos_data)} raw VOD entries")
            
        except Exception as e:
            print(f"❌ Parse Exception: {str(e)}")
            print(f"Raw response: {response.text[:300]}...")
            return jsonify({'success': False, 'error': f'Failed to parse response: {str(e)}'}), 500
        
        # Process VODs exactly like extension (background.js:488-527)
        hidden_vods = []
        for i, edge in enumerate(videos_data):
            node = edge.get('node', {})
            title = node.get('title', 'Untitled')
            
            print(f"\n📹 Processing VOD {i+1}: {title[:40]}...")
            
            # Get URLs
            animated_preview_url = node.get('animatedPreviewURL', '')
            preview_thumbnail_url = node.get('previewThumbnailURL', '')
            
            # Extract M3U8 path from animatedPreviewURL (extension line 489-490)
            m3u8_path = None
            if animated_preview_url:
                m3u8_match = re.search(r'(\w+\.cloudfront\.net\/\w{20}_\w+_\d+_\d+)(?=\/)', animated_preview_url)
                if m3u8_match:
                    m3u8_path = m3u8_match.group(1)
                    print(f"  ✅ M3U8 path: {m3u8_path}")
            
            # Extract tokens (extension lines 492-497)
            m3u8_tokens = None
            
            # Try previewThumbnailURL first
            if preview_thumbnail_url:
                thumbnail_path = re.search(r'(?<=\/)\w{20}_\w+_\d+_\d+(?=\/)', preview_thumbnail_url)
                if thumbnail_path:
                    tokens_match = re.search(r'(\w{20})_([_\w]+)_(\d+)_(\d+)', thumbnail_path.group(0))
                    if tokens_match:
                        m3u8_tokens = tokens_match.groups()
                        print(f"  ✅ Tokens from thumbnail: {m3u8_tokens}")
            
            # Fallback to animatedPreviewURL  
            if not m3u8_tokens and animated_preview_url:
                animated_path = re.search(r'(?<=\/)\w{20}_[_\w]+_\d+_\d+(?=\/)', animated_preview_url)
                if animated_path:
                    tokens_match = re.search(r'(\w{20})_([_\w]+)_(\d+)_(\d+)', animated_path.group(0))
                    if tokens_match:
                        m3u8_tokens = tokens_match.groups()
                        print(f"  ✅ Tokens from animated: {m3u8_tokens}")
            
            # Extract server (extension line 499-501)
            m3u8_server = None
            if animated_preview_url:
                server_match = re.search(r'(\w+)(?=\.cloudfront\.net\/\w{20}_[_\w]+_\d+_\d+\/)', animated_preview_url)
                if server_match:
                    m3u8_server = server_match.group(1)
                    print(f"  ✅ Server: {m3u8_server}")
            
            # Build VOD object if we have the necessary data
            if m3u8_path and m3u8_tokens:
                hash_token, channel_part, stream_id, timestamp_str = m3u8_tokens
                
                # Build exactly like extension (background.js:502-526)
                vod_timestamp = None
                if node.get('publishedAt'):
                    # Parse ISO timestamp
                    published_at = node['publishedAt']
                    vod_timestamp = int(time.mktime(time.strptime(published_at, '%Y-%m-%dT%H:%M:%SZ'))) * 1000
                elif timestamp_str:
                    vod_timestamp = int(timestamp_str) * 1000
                
                vod = {
                    # Core fields matching extension
                    'vod_id': node.get('id'),
                    'timestamp': vod_timestamp,
                    'published_at': node.get('publishedAt'),
                    'title': title,
                    'duration': node.get('lengthSeconds', 0) * 1000 if node.get('lengthSeconds') else 0,  # Extension uses milliseconds
                    'animated_preview_url': animated_preview_url,
                    'view_count': node.get('viewCount', 0),
                    'preview_url': preview_thumbnail_url,
                    
                    # M3U8 extraction results
                    'm3u8_path': m3u8_path,
                    'm3u8_tokens': list(m3u8_tokens),
                    'stream_id': stream_id,
                    'hash': hash_token,
                    'source': f"https://{m3u8_path}/chunked/index-dvr.m3u8",
                    'src': f"https://{m3u8_path}/chunked/index-dvr.m3u8",
                    'stream_start_seconds': int(timestamp_str) if timestamp_str else 0,
                    'timestamp_seconds': int(timestamp_str) if timestamp_str else 0,
                    'm3u8_server': m3u8_server,
                    'midpath': f"{hash_token}_{channel_login}_{stream_id}_{timestamp_str}",
                    'channel_login': channel_login,
                    
                    # Metadata
                    'is_hidden': True,
                    'extraction_method': 'thumbnail_urls'
                }
                
                hidden_vods.append(vod)
                print(f"  🎯 HIDDEN VOD FOUND: Stream ID {stream_id}, Duration: {vod['duration']/1000/60:.1f}min")
            else:
                print(f"  ❌ Skipped - missing m3u8_path or tokens")
        
        print(f"\n🎉 Successfully extracted {len(hidden_vods)} HIDDEN VODs!")
        
        return jsonify({
            'success': True,
            'videos': hidden_vods,
            'count': len(hidden_vods),
            'channel': channel_login,
            'extraction_method': 'extension_replica'
        })
        
    except Exception as e:
        print(f"❌ Error in get_hidden_vods: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@twitch_hidden_vods_bp.route('/api/twitch/test-vod-access/<channel_login>/<stream_id>', methods=['GET'])  
def test_vod_access(channel_login, stream_id):
    """Test if a specific hidden VOD is accessible"""
    try:
        # Try to access a constructed M3U8 URL 
        # This would need the hash and timestamp from the hidden VODs list
        return jsonify({
            'success': True,
            'message': 'Use the hidden-vods endpoint first to get stream details'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
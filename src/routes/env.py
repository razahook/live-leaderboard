import os
import requests
from flask import Blueprint, jsonify

env_bp = Blueprint('env', __name__)

@env_bp.route('/public-env', methods=['GET'])
def public_env():
    return jsonify({
        "success": True,
        "data": {
            "NEXT_PUBLIC_SUPABASE_URL": os.environ.get('NEXT_PUBLIC_SUPABASE_URL'),
            "NEXT_PUBLIC_SUPABASE_ANON_KEY": os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
        }
    })

@env_bp.route('/edge-config/public', methods=['GET'])
def edge_config_public():
    url = os.environ.get('EDGE_CONFIG')
    flags = {
        'enable_medal': True,  # Enable Medal.tv by default now
        'max_recent_clips': 4,
        'multistream_default_layout': 'equal',
        'feature_flags': {'multistreamDock': True, 'streamPage': False},
        'medal_config': {
            'default_category': '5FsRVgww4b',  # Apex Legends
            'filter_apex_only': True,
            'allow_user_imports': True,
            'max_clips_per_search': 20
        },
        'game_categories': {
            'apex_legends': '5FsRVgww4b',
            'valorant': 'fW3AZxHf_c', 
            'overwatch': 'some_id'
        }
    }
    if url:
        try:
            r = requests.get(url, timeout=3)
            if r.ok:
                data = r.json()
                if isinstance(data, dict):
                    # Merge known keys only
                    for k in flags.keys():
                        if k in data:
                            flags[k] = data[k]
        except Exception:
            pass
    return jsonify({'success': True, 'data': flags})


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
        'enable_medal': False,
        'max_recent_clips': 4,
        'multistream_default_layout': 'equal',
        'feature_flags': {'multistreamDock': True, 'streamPage': False}
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


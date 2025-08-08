import os
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


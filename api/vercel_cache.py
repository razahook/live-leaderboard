"""
Vercel-compatible cache manager for serverless functions.

This module provides in-memory caching that works with Vercel's serverless environment.
For production, consider using Redis or another external cache service.
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# In-memory cache for the serverless function
_memory_cache: Dict[str, Dict[str, Any]] = {}

# Cache configuration
CACHE_TTL = {
    'twitch_tokens': 3600,  # 1 hour
    'live_status': 300,     # 5 minutes
    'clips': 1800,          # 30 minutes
    'user_validation': 86400,  # 24 hours
    'vods': 3600,           # 1 hour
    'leaderboard': 300      # 5 minutes
}

class VercelCacheManager:
    """
    Vercel-compatible cache manager that uses in-memory storage
    with fallback to reading initial data from included cache files.
    """
    
    @staticmethod
    def get_cache_file_path(cache_type: str) -> str:
        """Get the path to a cache file in the api directory."""
        base_dir = os.path.dirname(__file__)
        cache_files = {
            'access_tokens': os.path.join(base_dir, 'cache', 'twitch', 'access_tokens.json'),
            'clips': os.path.join(base_dir, 'cache', 'twitch', 'clips.json'),
            'user_validation': os.path.join(base_dir, 'cache', 'twitch', 'user_validation.json'),
            'vods': os.path.join(base_dir, 'cache', 'twitch', 'vods.json'),
            'invalid_usernames': os.path.join(base_dir, 'cache', 'twitch', 'invalid_usernames.json')
        }
        return cache_files.get(cache_type, '')
    
    @staticmethod
    def load_initial_cache(cache_type: str) -> Dict[str, Any]:
        """Load initial cache data from included files (read-only)."""
        cache_file = VercelCacheManager.get_cache_file_path(cache_type)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    
                # Fix timestamp formats if needed
                if 'last_updated' in data:
                    try:
                        if isinstance(data['last_updated'], (int, float)):
                            # Convert Unix timestamp to ISO string for consistency
                            data['last_updated'] = datetime.fromtimestamp(data['last_updated']).isoformat()
                    except (ValueError, OSError) as e:
                        print(f"Warning: Could not convert timestamp {data['last_updated']}: {e}")
                        # Remove invalid timestamp
                        del data['last_updated']
                    
                return data
            except Exception as e:
                print(f"Warning: Could not load cache file {cache_file}: {e}")
        return {}
    
    @staticmethod
    def get(key: str, cache_type: str = 'default') -> Optional[Any]:
        """Get a value from the in-memory cache."""
        cache_key = f"{cache_type}:{key}"
        
        if cache_key in _memory_cache:
            entry = _memory_cache[cache_key]
            
            # Check if expired
            if entry['expires_at'] > time.time():
                return entry['data']
            else:
                # Remove expired entry
                del _memory_cache[cache_key]
        
        # If not in memory, try to load from initial cache files
        if cache_type in ['access_tokens', 'clips', 'user_validation', 'vods', 'invalid_usernames']:
            initial_data = VercelCacheManager.load_initial_cache(cache_type)
            if key in initial_data:
                # Cache it in memory for future use
                VercelCacheManager.set(key, initial_data[key], cache_type)
                return initial_data[key]
        
        return None
    
    @staticmethod
    def set(key: str, value: Any, cache_type: str = 'default', ttl: Optional[int] = None) -> None:
        """Set a value in the in-memory cache."""
        if ttl is None:
            ttl = CACHE_TTL.get(cache_type, 300)  # Default 5 minutes
        
        cache_key = f"{cache_type}:{key}"
        _memory_cache[cache_key] = {
            'data': value,
            'expires_at': time.time() + ttl,
            'created_at': time.time()
        }
    
    @staticmethod
    def delete(key: str, cache_type: str = 'default') -> None:
        """Delete a value from the in-memory cache."""
        cache_key = f"{cache_type}:{key}"
        if cache_key in _memory_cache:
            del _memory_cache[cache_key]
    
    @staticmethod
    def clear(cache_type: Optional[str] = None) -> None:
        """Clear cache entries."""
        if cache_type is None:
            _memory_cache.clear()
        else:
            keys_to_delete = [k for k in _memory_cache.keys() if k.startswith(f"{cache_type}:")]
            for key in keys_to_delete:
                del _memory_cache[key]
    
    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """Get cache statistics."""
        now = time.time()
        active_entries = 0
        expired_entries = 0
        
        for entry in _memory_cache.values():
            if entry['expires_at'] > now:
                active_entries += 1
            else:
                expired_entries += 1
        
        return {
            'total_entries': len(_memory_cache),
            'active_entries': active_entries,
            'expired_entries': expired_entries,
            'cache_types': list(set(k.split(':')[0] for k in _memory_cache.keys()))
        }

# Legacy compatibility functions for existing code
def load_cache_file(file_path: str) -> Dict[str, Any]:
    """
    Legacy function for backward compatibility.
    Maps to the new cache system.
    """
    # Extract cache type from file path
    if 'access_tokens' in file_path:
        return VercelCacheManager.load_initial_cache('access_tokens')
    elif 'clips' in file_path:
        return VercelCacheManager.load_initial_cache('clips')
    elif 'user_validation' in file_path:
        return VercelCacheManager.load_initial_cache('user_validation')
    elif 'vods' in file_path:
        return VercelCacheManager.load_initial_cache('vods')
    elif 'invalid_usernames' in file_path:
        return VercelCacheManager.load_initial_cache('invalid_usernames')
    else:
        return {}

def save_cache_file(file_path: str, data: Dict[str, Any]) -> None:
    """
    Legacy function for backward compatibility.
    In Vercel, this just logs a warning since we can't write files.
    """
    print(f"Warning: save_cache_file called in Vercel environment. Data not persisted: {file_path}")
    # In a real production environment, you would save this to Redis or another external service

# Legacy leaderboard cache for backward compatibility
leaderboard_cache = {
    "data": None,
    "last_updated": None
}

# Initialize cache with any existing data
def init_vercel_cache():
    """Initialize the Vercel cache system."""
    print("Initializing Vercel cache system...")
    
    # Pre-load critical cache data with error handling
    for cache_type in ['access_tokens', 'user_validation']:
        try:
            initial_data = VercelCacheManager.load_initial_cache(cache_type)
            for key, value in initial_data.items():
                # Skip metadata fields like 'last_updated' when setting cache
                if key not in ['last_updated']:
                    VercelCacheManager.set(key, value, cache_type)
        except Exception as e:
            print(f"Warning: Failed to load initial cache for {cache_type}: {e}")
    
    print(f"Cache initialized with stats: {VercelCacheManager.get_stats()}")

# Auto-initialize when imported
init_vercel_cache()

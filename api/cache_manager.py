# Enhanced cache manager with different TTLs for different data types
from datetime import datetime, timedelta
import json
import os
import threading
import logging
from typing import Any, Optional, Dict, Union
from enum import Enum

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CacheType(Enum):
    """Enum for different cache types with their default TTLs"""
    LIVE_DATA = 30        # 30 seconds for live streams, current matches
    STATIC_DATA = 300     # 5 minutes for leaderboards, player stats
    USER_DATA = 3600      # 1 hour for user preferences, settings
    TWITCH_API = 900      # 15 minutes for Twitch API responses
    CLIPS_DATA = 1800     # 30 minutes for clips data
    VOD_DATA = 7200       # 2 hours for VOD data

class EnhancedCache:
    """Enhanced cache with TTL support, threading safety, and different cache types"""
    
    def __init__(self, cache_type: CacheType = CacheType.STATIC_DATA, custom_ttl: Optional[int] = None):
        self.cache_type = cache_type
        self.ttl = custom_ttl if custom_ttl is not None else cache_type.value
        self.data = None
        self.last_updated = None
        self.lock = threading.RLock()
        self.hit_count = 0
        self.miss_count = 0
        self.metadata = {}
    
    def is_expired(self) -> bool:
        """Check if cache is expired"""
        with self.lock:
            if self.last_updated is None:
                return True
            return datetime.now() - self.last_updated > timedelta(seconds=self.ttl)
    
    def get_data(self, default: Any = None) -> Any:
        """Get cached data if not expired"""
        with self.lock:
            if self.is_expired():
                self.miss_count += 1
                return default
            
            self.hit_count += 1
            return self.data
    
    def set_data(self, data: Any, metadata: Optional[Dict] = None) -> None:
        """Set cache data with optional metadata"""
        with self.lock:
            self.data = data
            self.last_updated = datetime.now()
            if metadata:
                self.metadata.update(metadata)
            
            logger.debug(f"Cache updated for {self.cache_type.name} at {self.last_updated}")
    
    def clear(self) -> None:
        """Clear cache data"""
        with self.lock:
            self.data = None
            self.last_updated = None
            self.metadata.clear()
            logger.debug(f"Cache cleared for {self.cache_type.name}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            total_requests = self.hit_count + self.miss_count
            hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'cache_type': self.cache_type.name,
                'ttl_seconds': self.ttl,
                'has_data': self.data is not None,
                'last_updated': self.last_updated.isoformat() if self.last_updated else None,
                'is_expired': self.is_expired(),
                'hit_count': self.hit_count,
                'miss_count': self.miss_count,
                'hit_rate_percent': round(hit_rate, 2),
                'metadata': self.metadata.copy()
            }
    
    def refresh_if_expired(self, refresh_func, *args, **kwargs) -> Any:
        """Refresh cache data if expired using provided function"""
        if self.is_expired():
            try:
                new_data = refresh_func(*args, **kwargs)
                self.set_data(new_data, {'refreshed_at': datetime.now().isoformat()})
                logger.info(f"Cache refreshed for {self.cache_type.name}")
                return new_data
            except Exception as e:
                logger.error(f"Failed to refresh cache for {self.cache_type.name}: {str(e)}")
                return self.data  # Return stale data if refresh fails
        
        return self.get_data()

class PersistentCache(EnhancedCache):
    """Enhanced cache with file persistence"""
    
    def __init__(self, cache_type: CacheType, cache_file: str, custom_ttl: Optional[int] = None):
        super().__init__(cache_type, custom_ttl)
        self.cache_file = cache_file
        self.load_from_file()
    
    def load_from_file(self) -> None:
        """Load cache data from file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # Check if file data is still valid
                if 'last_updated' in cache_data and cache_data['last_updated']:
                    try:
                        last_updated = datetime.fromisoformat(cache_data['last_updated'])
                        if datetime.now() - last_updated <= timedelta(seconds=self.ttl):
                            self.data = cache_data.get('data')
                            self.last_updated = last_updated
                            self.metadata = cache_data.get('metadata', {})
                            logger.debug(f"Loaded valid cache from {self.cache_file}")
                            return
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid timestamp in cache file {self.cache_file}: {e}")
                
                logger.debug(f"Cache file {self.cache_file} is expired, clearing")
                
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to load cache from {self.cache_file}: {str(e)}")
    
    def set_data(self, data: Any, metadata: Optional[Dict] = None) -> None:
        """Set cache data and persist to file"""
        super().set_data(data, metadata)
        self.save_to_file()
    
    def save_to_file(self) -> None:
        """Save cache data to file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            
            cache_data = {
                'data': self.data,
                'last_updated': self.last_updated.isoformat() if self.last_updated else None,
                'metadata': self.metadata,
                'cache_type': self.cache_type.name,
                'ttl': self.ttl
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Cache saved to {self.cache_file}")
            
        except Exception as e:
            logger.error(f"Failed to save cache to {self.cache_file}: {str(e)}")
    
    def clear(self) -> None:
        """Clear cache and remove file"""
        super().clear()
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
                logger.debug(f"Cache file {self.cache_file} removed")
        except Exception as e:
            logger.error(f"Failed to remove cache file {self.cache_file}: {str(e)}")

class CacheManager:
    """Central cache manager for the application"""
    
    def __init__(self, cache_base_dir: str):
        self.cache_dir = cache_base_dir
        self.caches: Dict[str, Union[EnhancedCache, PersistentCache]] = {}
        self._setup_default_caches()
    
    def _setup_default_caches(self) -> None:
        """Setup default caches for the application"""
        # In-memory caches
        self.caches['leaderboard'] = EnhancedCache(CacheType.STATIC_DATA)
        self.caches['live_streams'] = EnhancedCache(CacheType.LIVE_DATA)
        self.caches['user_preferences'] = EnhancedCache(CacheType.USER_DATA)
        
        # Persistent caches
        twitch_cache_dir = os.path.join(self.cache_dir, 'twitch')
        self.caches['twitch_tokens'] = PersistentCache(
            CacheType.TWITCH_API,
            os.path.join(twitch_cache_dir, 'access_tokens.json')
        )
        self.caches['twitch_clips'] = PersistentCache(
            CacheType.CLIPS_DATA,
            os.path.join(twitch_cache_dir, 'clips.json')
        )
        self.caches['twitch_vods'] = PersistentCache(
            CacheType.VOD_DATA,
            os.path.join(twitch_cache_dir, 'vods.json')
        )
        self.caches['user_validation'] = PersistentCache(
            CacheType.USER_DATA,
            os.path.join(twitch_cache_dir, 'user_validation.json')
        )
    
    def get_cache(self, cache_name: str) -> Optional[Union[EnhancedCache, PersistentCache]]:
        """Get a specific cache by name"""
        return self.caches.get(cache_name)
    
    def create_cache(self, name: str, cache_type: CacheType, persistent: bool = False, 
                    custom_ttl: Optional[int] = None) -> Union[EnhancedCache, PersistentCache]:
        """Create a new cache"""
        if persistent:
            cache_file = os.path.join(self.cache_dir, f"{name}.json")
            cache = PersistentCache(cache_type, cache_file, custom_ttl)
        else:
            cache = EnhancedCache(cache_type, custom_ttl)
        
        self.caches[name] = cache
        return cache
    
    def clear_all_caches(self) -> None:
        """Clear all caches"""
        for cache in self.caches.values():
            cache.clear()
        logger.info("All caches cleared")
    
    def clear_expired_caches(self) -> int:
        """Clear all expired caches and return count"""
        cleared_count = 0
        for name, cache in self.caches.items():
            if cache.is_expired():
                cache.clear()
                cleared_count += 1
                logger.debug(f"Cleared expired cache: {name}")
        
        return cleared_count
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all caches"""
        stats = {}
        for name, cache in self.caches.items():
            stats[name] = cache.get_stats()
        
        return stats
    
    def cleanup_old_files(self, max_age_days: int = 7) -> int:
        """Cleanup old cache files and return count of removed files"""
        removed_count = 0
        cutoff_time = datetime.now() - timedelta(days=max_age_days)
        
        try:
            for root, dirs, files in os.walk(self.cache_dir):
                for file in files:
                    if file.endswith('.json'):
                        file_path = os.path.join(root, file)
                        if os.path.getmtime(file_path) < cutoff_time.timestamp():
                            os.remove(file_path)
                            removed_count += 1
                            logger.debug(f"Removed old cache file: {file_path}")
        
        except Exception as e:
            logger.error(f"Error during cache cleanup: {str(e)}")
        
        return removed_count

# Global cache manager instance
cache_base_dir = os.path.join(os.path.dirname(__file__), 'cache')
cache_manager = CacheManager(cache_base_dir)

# Backward compatibility - keep the old leaderboard_cache
LeaderboardCache = EnhancedCache  # For backward compatibility
leaderboard_cache = cache_manager.get_cache('leaderboard')

# Convenience functions for easy access
def get_live_cache():
    """Get cache for live data (30s TTL)"""
    return cache_manager.get_cache('live_streams')

def get_static_cache():
    """Get cache for static data (5min TTL)"""
    return cache_manager.get_cache('leaderboard')

def get_user_cache():
    """Get cache for user data (1hr TTL)"""
    return cache_manager.get_cache('user_preferences')

def get_twitch_cache(cache_type: str = 'tokens'):
    """Get Twitch-specific cache"""
    return cache_manager.get_cache(f'twitch_{cache_type}')

def clear_all_caches():
    """Clear all application caches"""
    cache_manager.clear_all_caches()

def get_cache_stats():
    """Get statistics for all caches"""
    return cache_manager.get_all_stats()
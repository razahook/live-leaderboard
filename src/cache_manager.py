# src/cache_manager.py
from datetime import datetime

class LeaderboardCache:
    """Simple cache for leaderboard data with TTL"""
    
    def __init__(self, ttl_seconds=300):  # 5 minutes default TTL
        self.data = None
        self.last_updated = None
        self.ttl_seconds = ttl_seconds
    
    def get_data(self):
        """Get cached data if valid, None if expired or empty"""
        if self.data is None or self.last_updated is None:
            return None
            
        # Check if cache is expired
        if (datetime.now() - self.last_updated).total_seconds() > self.ttl_seconds:
            return None
            
        return self.data
    
    def set_data(self, data):
        """Set cache data and update timestamp"""
        self.data = data
        self.last_updated = datetime.now()
    
    def clear(self):
        """Clear cache data"""
        self.data = None
        self.last_updated = None

# Global cache instance
leaderboard_cache = LeaderboardCache()
from datetime import datetime

class LeaderboardCache:
    def __init__(self):
        self.data = None
        self.last_updated = None
        self.cache_duration = 300  # 5 minutes in seconds
    
    def get_data(self):
        """Get cached data if it's still valid, otherwise return None"""
        if (self.data and self.last_updated and 
            (datetime.now() - self.last_updated).seconds < self.cache_duration):
            return self.data
        return None
    
    def set_data(self, data):
        """Set cache data and update timestamp"""
        self.data = data
        self.last_updated = datetime.now()
    
    def clear(self):
        """Clear the cache"""
        self.data = None
        self.last_updated = None

# Global instance
leaderboard_cache = LeaderboardCache()
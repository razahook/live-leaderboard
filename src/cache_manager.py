# src/cache_manager.py
from datetime import datetime, timedelta

class LeaderboardCache:
    def __init__(self, cache_duration=300):
        self.data = None
        self.last_updated = None
        self.cache_duration = cache_duration
    
    def is_expired(self):
        if self.last_updated is None:
            return True
        return datetime.now() - self.last_updated > timedelta(seconds=self.cache_duration)
    
    def get_data(self):
        if self.is_expired():
            return None
        return self.data
    
    def set_data(self, data):
        self.data = data
        self.last_updated = datetime.now()

# Global instance
leaderboard_cache = LeaderboardCache()
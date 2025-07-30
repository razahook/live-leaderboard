from datetime import datetime, timedelta


class LeaderboardCache:
    """Cache for leaderboard data with automatic expiration."""
    
    def __init__(self, cache_duration=300):
        self.data = None
        self.last_updated = None
        self.cache_duration = cache_duration

    def is_expired(self):
        """Check if the cache has expired."""
        if self.last_updated is None:
            return True
        return datetime.now() - self.last_updated > timedelta(seconds=self.cache_duration)

    def get_data(self):
        """Get cached data if it's still valid, otherwise return None."""
        if self.is_expired():
            return None
        return self.data

    def set_data(self, data):
        """Store data in cache with current timestamp."""
        self.data = data
        self.last_updated = datetime.now()

    def clear(self):
        """Clear the cache."""
        self.data = None
        self.last_updated = None


# Global cache instance
leaderboard_cache = LeaderboardCache()
class LeaderboardCache:
    """Simple in-process cache for leaderboard data with TTL handling.

    This implementation mirrors the class that existed in api/index.py so the two
    locations can share the same behaviour.  In addition we expose __getitem__
    and __setitem__ so that code which (incorrectly) treats the cache like a
    dictionary continues to work without modification. This eliminates runtime
    KeyErrors while we progressively migrate the codebase to the attribute
    interface (leaderboard_cache.data etc.).
    """

    def __init__(self, cache_duration: int = 300):
        # The actual payload scraped from apexlegendsstatus.com
        self.data = None
        # datetime instance when the cache was last updated
        self.last_updated = None
        # cache expiration time in seconds
        self.cache_duration = cache_duration

    # ---------------------------------------------------------------------
    # Public helpers (attribute API)
    # ---------------------------------------------------------------------
    def is_expired(self) -> bool:
        """Return True if the cache is empty or the TTL has elapsed."""
        from datetime import datetime, timedelta

        if self.last_updated is None:
            return True
        return datetime.now() - self.last_updated > timedelta(seconds=self.cache_duration)

    def get_data(self):
        """Return cached payload or None if cache is expired."""
        if self.is_expired():
            return None
        return self.data

    def set_data(self, data):
        """Store data inside the cache and stamp the current time."""
        from datetime import datetime

        self.data = data
        self.last_updated = datetime.now()

    # ------------------------------------------------------------------
    # Dict shim – keeps legacy code that uses [] working
    # ------------------------------------------------------------------
    def __getitem__(self, key):
        if key == "data":
            return self.data
        if key == "last_updated":
            return self.last_updated
        raise KeyError(key)

    def __setitem__(self, key, value):
        if key == "data":
            self.data = value
            return
        if key == "last_updated":
            self.last_updated = value
            return
        raise KeyError(key)


# Single shared instance used across the entire application
leaderboard_cache = LeaderboardCache()
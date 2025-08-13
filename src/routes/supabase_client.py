import os
from functools import lru_cache


@lru_cache(maxsize=1)
def get_supabase():
    """Create and cache a Supabase client using service role if available.

    Falls back to public anon key for read-only operations. For secure writes,
    you should provide SUPABASE_SERVICE_ROLE in the environment.
    """
    url = os.environ.get('SUPABASE_URL') or os.environ.get('NEXT_PUBLIC_SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_SERVICE_ROLE') or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


def ensure_tables():
    """Optionally create tables if they do not exist (best effort, idempotent).

    Recommended to create schema via SQL in Supabase. This is a helper to reduce
    manual steps in dev; production should manage schema via migrations.
    """
    client = get_supabase()
    if client is None:
        return False
    # We avoid running DDL here; leave schema creation to SQL migrations.
    return True



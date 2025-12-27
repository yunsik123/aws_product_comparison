"""TTL cache and rate limiting."""
import time
import hashlib
import json
import sqlite3
import threading
from typing import Optional, Any, Dict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .config import get_settings


@dataclass
class CacheEntry:
    """Cache entry with value and expiration."""
    value: Any
    expires_at: float


class InMemoryCache:
    """Thread-safe in-memory LRU cache with TTL."""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 900):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
    
    def _make_key(self, *args, **kwargs) -> str:
        """Create a cache key from arguments."""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            
            if time.time() > entry.expires_at:
                # Expired, remove it
                del self._cache[key]
                return None
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL."""
        ttl = ttl or self._ttl_seconds
        expires_at = time.time() + ttl
        
        with self._lock:
            # Evict oldest if at capacity
            if len(self._cache) >= self._max_size and key not in self._cache:
                self._evict_oldest()
            
            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)
    
    def _evict_oldest(self) -> None:
        """Evict the oldest cache entry."""
        if not self._cache:
            return
        
        # Find oldest by expiration
        oldest_key = min(self._cache.keys(), 
                        key=lambda k: self._cache[k].expires_at)
        del self._cache[oldest_key]
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()


class RateLimiter:
    """Rate limiter for force refresh requests."""
    
    def __init__(self, window_seconds: int = 60):
        self._last_refresh: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._window_seconds = window_seconds
    
    def check_and_update(self, key: str) -> tuple[bool, int]:
        """Check if action is allowed and update timestamp.
        
        Returns:
            Tuple of (allowed, seconds_until_allowed)
        """
        now = time.time()
        
        with self._lock:
            last_time = self._last_refresh.get(key, 0)
            elapsed = now - last_time
            
            if elapsed >= self._window_seconds:
                self._last_refresh[key] = now
                return True, 0
            else:
                remaining = int(self._window_seconds - elapsed)
                return False, remaining


class SQLiteCache:
    """Persistent SQLite cache for longer-term storage."""
    
    def __init__(self, db_path: str = "cache.db"):
        self._db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    expires_at REAL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires 
                ON cache(expires_at)
            """)
            conn.commit()
    
    def get(self, key: str) -> Optional[str]:
        """Get value from cache if not expired."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            value, expires_at = row
            if time.time() > expires_at:
                # Expired, delete it
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
                return None
            
            return value
    
    def set(self, key: str, value: str, ttl_seconds: int = 900) -> None:
        """Set value in cache with TTL."""
        expires_at = time.time() + ttl_seconds
        
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO cache (key, value, expires_at) 
                   VALUES (?, ?, ?)""",
                (key, value, expires_at)
            )
            conn.commit()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count of removed entries."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE expires_at < ?",
                (time.time(),)
            )
            conn.commit()
            return cursor.rowcount


# Global instances
_cache = InMemoryCache()
_rate_limiter = RateLimiter()
_sqlite_cache: Optional[SQLiteCache] = None


def get_cache() -> InMemoryCache:
    """Get the global cache instance."""
    return _cache


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return _rate_limiter


def get_sqlite_cache() -> SQLiteCache:
    """Get the SQLite cache instance (lazy init)."""
    global _sqlite_cache
    if _sqlite_cache is None:
        _sqlite_cache = SQLiteCache()
    return _sqlite_cache


def make_cache_key(brand_a: str, product_a: str, brand_b: str, product_b: str, sources: list) -> str:
    """Create a cache key for a comparison request."""
    key_data = {
        "brand_a": brand_a.lower(),
        "product_a": product_a.lower(),
        "brand_b": brand_b.lower(),
        "product_b": product_b.lower(),
        "sources": sorted(sources)
    }
    return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()

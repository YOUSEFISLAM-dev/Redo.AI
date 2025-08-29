from collections import defaultdict
from datetime import datetime, timedelta
import time
import threading
import os
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self):
        # In-memory storage for rate limiting (in production, use Redis)
        self.user_requests = defaultdict(list)
        self.ip_requests = defaultdict(list)
        self.lock = threading.Lock()
        
        # Configuration from environment
        self.messages_per_30s = int(os.getenv('RATE_LIMIT_MESSAGES_PER_30S', 5))
        self.messages_per_day = int(os.getenv('RATE_LIMIT_MESSAGES_PER_DAY', 100))
        
        # Cleanup old entries every 10 minutes
        self.last_cleanup = time.time()
        self.cleanup_interval = 600  # 10 minutes
    
    def _cleanup_old_entries(self):
        """Remove old entries to prevent memory leaks."""
        current_time = time.time()
        
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        with self.lock:
            # Clean entries older than 24 hours
            cutoff_time = current_time - 86400  # 24 hours
            
            for user_id in list(self.user_requests.keys()):
                self.user_requests[user_id] = [
                    req_time for req_time in self.user_requests[user_id]
                    if req_time > cutoff_time
                ]
                if not self.user_requests[user_id]:
                    del self.user_requests[user_id]
            
            for ip in list(self.ip_requests.keys()):
                self.ip_requests[ip] = [
                    req_time for req_time in self.ip_requests[ip]
                    if req_time > cutoff_time
                ]
                if not self.ip_requests[ip]:
                    del self.ip_requests[ip]
            
            self.last_cleanup = current_time
    
    def check_rate_limit(self, user_id: str, ip_address: str) -> tuple[bool, str]:
        """
        Check if user/IP is within rate limits.
        Returns (allowed, error_message)
        """
        self._cleanup_old_entries()
        
        current_time = time.time()
        
        with self.lock:
            # Check 30-second limit for user
            user_recent = [
                req_time for req_time in self.user_requests[user_id]
                if req_time > current_time - 30
            ]
            
            if len(user_recent) >= self.messages_per_30s:
                return False, f"Rate limit exceeded: {self.messages_per_30s} messages per 30 seconds"
            
            # Check daily limit for user
            user_daily = [
                req_time for req_time in self.user_requests[user_id]
                if req_time > current_time - 86400
            ]
            
            if len(user_daily) >= self.messages_per_day:
                return False, f"Daily rate limit exceeded: {self.messages_per_day} messages per day"
            
            # Check IP rate limits (more aggressive)
            ip_recent = [
                req_time for req_time in self.ip_requests[ip_address]
                if req_time > current_time - 30
            ]
            
            if len(ip_recent) >= self.messages_per_30s * 2:  # 2x user limit for IP
                return False, "IP rate limit exceeded"
            
            return True, ""
    
    def record_request(self, user_id: str, ip_address: str):
        """Record a successful request for rate limiting."""
        current_time = time.time()
        
        with self.lock:
            self.user_requests[user_id].append(current_time)
            self.ip_requests[ip_address].append(current_time)
            
            # Keep only recent entries
            self.user_requests[user_id] = [
                req_time for req_time in self.user_requests[user_id]
                if req_time > current_time - 86400
            ]
            self.ip_requests[ip_address] = [
                req_time for req_time in self.ip_requests[ip_address]
                if req_time > current_time - 86400
            ]
    
    def get_user_stats(self, user_id: str) -> dict:
        """Get current rate limit stats for a user."""
        current_time = time.time()
        
        with self.lock:
            user_recent = len([
                req_time for req_time in self.user_requests[user_id]
                if req_time > current_time - 30
            ])
            
            user_daily = len([
                req_time for req_time in self.user_requests[user_id]
                if req_time > current_time - 86400
            ])
            
            return {
                'messages_last_30s': user_recent,
                'max_messages_30s': self.messages_per_30s,
                'messages_today': user_daily,
                'max_messages_daily': self.messages_per_day,
                'can_send': user_recent < self.messages_per_30s and user_daily < self.messages_per_day
            }

# Global instance
rate_limiter = RateLimiter()
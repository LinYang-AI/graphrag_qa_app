import re
import html
from typing import Any, Dict, List
import sqlparse
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class SecurityValidator:
    """Input validation and sanitization"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_password(password: str) -> Dict[str, Any]:
        """Validate password strength"""
        issues = []
        
        if len(password) < 8:
            issues.append("Password must be at least 8 characters long")
        
        if not re.search(r'[A-Z]', password):
            issues.append("Password must contain at least one uppercase letter")
        
        if not re.search(r'[a-z]', password):
            issues.append("Password must contain at least one lowercase letter")
        
        if not re.search(r'\d', password):
            issues.append("Password must contain at least one digit")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            issues.append("Password must contain at least one special character")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }
    
    @staticmethod
    def sanitize_string(input_str: str, max_length: int = 1000) -> str:
        """Sanitize string input"""
        if not input_str:
            return ""
        
        # Truncate to max length
        sanitized = input_str[:max_length]
        
        # HTML escape
        sanitized = html.escape(sanitized)
        
        # Remove potential script injection
        sanitized = re.sub(r'<script.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        return sanitized.strip()
    
    @staticmethod
    def validate_tenant_id(tenant_id: str) -> bool:
        """Validate tenant ID format"""
        # Alphanumeric and underscores only, 3-50 characters
        pattern = r'^[a-zA-Z0-9_]{3,50}$'
        return re.match(pattern, tenant_id) is not None
    
    @staticmethod
    def detect_sql_injection(query: str) -> bool:
        """Detect potential SQL injection attempts"""
        dangerous_patterns = [
            r'\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b',
            r'[\'"]\s*;\s*--',
            r'\b(OR|AND)\s+\d+\s*=\s*\d+',
            r'\bEXEC\s*\(',
        ]
        
        query_upper = query.upper()
        for pattern in dangerous_patterns:
            if re.search(pattern, query_upper):
                logger.warning(f"Potential SQL injection detected: {query[:100]}")
                return True
        
        return False
    
    @staticmethod
    def validate_file_upload(filename: str, file_size: int, max_size_mb: int = 50) -> Dict[str, Any]:
        """Validate file upload"""
        issues = []
        
        # Check file size
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            issues.append(f"File size exceeds {max_size_mb}MB limit")
        
        # Check file extension
        allowed_extensions = {'.txt', '.pdf', '.docx', '.md', '.html', '.csv', '.xlsx'}
        file_ext = '.' + filename.split('.')[-1].lower() if '.' in filename else ''
        
        if file_ext not in allowed_extensions:
            issues.append(f"File type {file_ext} not allowed")
        
        # Check filename for dangerous characters
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
        if any(char in filename for char in dangerous_chars):
            issues.append("Filename contains invalid characters")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }

class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self):
        self.requests = {}  # {user_id: [(timestamp, endpoint), ...]}
        
    def is_allowed(self, user_id: str, endpoint: str, max_requests: int = 100, 
                   window_minutes: int = 60) -> bool:
        """Check if request is allowed based on rate limits"""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        window_start = now - timedelta(minutes=window_minutes)
        
        # Clean old requests
        if user_id in self.requests:
            self.requests[user_id] = [
                (timestamp, ep) for timestamp, ep in self.requests[user_id]
                if timestamp > window_start
            ]
        else:
            self.requests[user_id] = []
        
        # Count requests for this endpoint
        endpoint_requests = [
            timestamp for timestamp, ep in self.requests[user_id]
            if ep == endpoint
        ]
        
        if len(endpoint_requests) >= max_requests:
            logger.warning(f"Rate limit exceeded for user {user_id} on {endpoint}")
            return False
        
        # Add current request
        self.requests[user_id].append((now, endpoint))
        return True

# Global instances
security_validator = SecurityValidator()
rate_limiter = RateLimiter()
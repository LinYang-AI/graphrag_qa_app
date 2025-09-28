import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class UserRole(Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"

class TenantPermission(Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"

class AuthConfig:
    """Authentication configuration"""
    SECRET_KEY = "your-super-secret-jwt-key-change-in-production"  # Change this!
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 7

class User:
    """User model"""
    def __init__(self, user_id: str, email: str, role: UserRole, 
                 tenant_id: str, permissions: List[TenantPermission]):
        self.user_id = user_id
        self.email = email
        self.role = role
        self.tenant_id = tenant_id
        self.permissions = permissions
        self.created_at = datetime.now(timezone.utc)

class AuthManager:
    """Handles authentication and authorization"""
    
    def __init__(self):
        self.users = {}  # In production, use a proper database
        self.refresh_tokens = {}
        
        # Create default admin user
        self.create_user("admin@example.com", "admin123", UserRole.ADMIN, "system", 
                        [TenantPermission.READ, TenantPermission.WRITE, TenantPermission.ADMIN])

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

    def create_user(self, email: str, password: str, role: UserRole, 
                   tenant_id: str, permissions: List[TenantPermission]) -> User:
        """Create a new user"""
        if email in self.users:
            raise ValueError("User already exists")
        
        user_id = f"user_{len(self.users) + 1}"
        hashed_password = self.hash_password(password)
        
        user = User(user_id, email, role, tenant_id, permissions)
        self.users[email] = {
            'user': user,
            'password_hash': hashed_password
        }
        
        logger.info(f"Created user: {email} with role {role.value} for tenant {tenant_id}")
        return user

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        user_data = self.users.get(email)
        if not user_data:
            return None
        
        if self.verify_password(password, user_data['password_hash']):
            return user_data['user']
        
        return None

    def create_access_token(self, user: User) -> str:
        """Create JWT access token"""
        expire = datetime.now(timezone.utc) + timedelta(minutes=AuthConfig.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        payload = {
            "sub": user.user_id,
            "email": user.email,
            "role": user.role.value,
            "tenant_id": user.tenant_id,
            "permissions": [p.value for p in user.permissions],
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "access"
        }
        
        return jwt.encode(payload, AuthConfig.SECRET_KEY, algorithm=AuthConfig.ALGORITHM)

    def create_refresh_token(self, user: User) -> str:
        """Create JWT refresh token"""
        expire = datetime.now(timezone.utc) + timedelta(days=AuthConfig.REFRESH_TOKEN_EXPIRE_DAYS)
        
        payload = {
            "sub": user.user_id,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh"
        }
        
        token = jwt.encode(payload, AuthConfig.SECRET_KEY, algorithm=AuthConfig.ALGORITHM)
        self.refresh_tokens[token] = user.user_id
        return token

    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, AuthConfig.SECRET_KEY, algorithms=[AuthConfig.ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

    def get_user_from_token(self, token: str) -> Optional[User]:
        """Get user from JWT token"""
        payload = self.verify_token(token)
        if not payload:
            return None
        
        # Find user by email (in production, use user_id)
        for email, user_data in self.users.items():
            if user_data['user'].user_id == payload['sub']:
                return user_data['user']
        
        return None

# Global auth manager instance
auth_manager = AuthManager()

# FastAPI security scheme
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Dependency to get current authenticated user"""
    token = credentials.credentials
    user = auth_manager.get_user_from_token(token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    return user

async def require_role(required_role: UserRole):
    """Dependency factory for role-based access control"""
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role != required_role and current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker

async def require_permission(required_permission: TenantPermission):
    """Dependency factory for permission-based access control"""
    def permission_checker(current_user: User = Depends(get_current_user)):
        if required_permission not in current_user.permissions and UserRole.ADMIN != current_user.role:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return permission_checker

async def require_tenant_access(request: Request, current_user: User = Depends(get_current_user)):
    """Ensure user can only access their tenant's data"""
    # Extract tenant_id from request (query param, path param, or body)
    tenant_id = None
    
    # Try to get from path parameters
    if hasattr(request, 'path_params') and 'tenant_id' in request.path_params:
        tenant_id = request.path_params['tenant_id']
    
    # Try to get from query parameters
    if not tenant_id:
        tenant_id = request.query_params.get('tenant_id')
    
    # Admin users can access any tenant
    if current_user.role == UserRole.ADMIN:
        return current_user
    
    # Regular users can only access their own tenant
    if tenant_id and tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied to this tenant")
    
    return current_user
class AuthManager {
  constructor() {
    this.API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';
    this.token = localStorage.getItem('admin_token');
    this.refreshToken = localStorage.getItem('admin_refresh_token');
    this.user = JSON.parse(localStorage.getItem('admin_user') || 'null');
  }

  // Check if user is authenticated
  isAuthenticated() {
    return !!this.token && !!this.user;
  }

  // Check if user is admin
  isAdmin() {
    return this.user?.role === 'admin';
  }

  // Get current user
  getCurrentUser() {
    return this.user;
  }

  // Get auth headers
  getAuthHeaders() {
    return this.token ? {
      'Authorization': `Bearer ${this.token}`,
      'Content-Type': 'application/json'
    } : {
      'Content-Type': 'application/json'
    };
  }

  // Login method
  async login(email, password) {
    try {
      const response = await fetch(`${this.API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Login failed');
      }

      const data = await response.json();
      
      // Store tokens and user info
      this.token = data.access_token;
      this.refreshToken = data.refresh_token;
      this.user = data.user;

      localStorage.setItem('admin_token', this.token);
      localStorage.setItem('admin_refresh_token', this.refreshToken);
      localStorage.setItem('admin_user', JSON.stringify(this.user));

      return data;
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  }

  // Logout method
  logout() {
    this.token = null;
    this.refreshToken = null;
    this.user = null;
    
    localStorage.removeItem('admin_token');
    localStorage.removeItem('admin_refresh_token');
    localStorage.removeItem('admin_user');
  }

  // Refresh access token
  async refreshAccessToken() {
    try {
      if (!this.refreshToken) {
        throw new Error('No refresh token available');
      }

      const response = await fetch(`${this.API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: this.refreshToken })
      });

      if (!response.ok) {
        throw new Error('Token refresh failed');
      }

      const data = await response.json();
      this.token = data.access_token;
      localStorage.setItem('admin_token', this.token);

      return data.access_token;
    } catch (error) {
      console.error('Token refresh error:', error);
      this.logout(); // Clear invalid tokens
      throw error;
    }
  }

  // API request with automatic token refresh
  async apiRequest(endpoint, options = {}) {
    const url = `${this.API_BASE}${endpoint}`;
    
    const requestOptions = {
      ...options,
      headers: {
        ...this.getAuthHeaders(),
        ...options.headers
      }
    };

    try {
      let response = await fetch(url, requestOptions);
      
      // If token expired, try to refresh
      if (response.status === 401 && this.refreshToken) {
        await this.refreshAccessToken();
        requestOptions.headers = {
          ...this.getAuthHeaders(),
          ...options.headers
        };
        response = await fetch(url, requestOptions);
      }

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || error.message || 'Request failed');
      }

      return await response.json();
    } catch (error) {
      console.error(`API request error for ${endpoint}:`, error);
      throw error;
    }
  }
}

// Admin API class
class AdminAPI {
  constructor(authManager) {
    this.auth = authManager;
  }

  // Document Management
  async uploadDocument(file, tenantId = 'default') {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('tenant_id', tenantId);

    return this.auth.apiRequest('/admin/upload', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.auth.token}`
      },
      body: formData
    });
  }

  async deleteDocument(documentHash) {
    return this.auth.apiRequest(`/admin/documents/${documentHash}`, {
      method: 'DELETE'
    });
  }

  async getDocuments(tenantId = 'default', limit = 20) {
    return this.auth.apiRequest(`/documents?tenant_id=${tenantId}&limit=${limit}`);
  }

  // User Management
  async getUsers() {
    return this.auth.apiRequest('/admin/users');
  }

  async createUser(userData) {
    return this.auth.apiRequest('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData)
    });
  }

  // System Stats
  async getSystemStats() {
    return this.auth.apiRequest('/admin/stats');
  }

  async getGraphOverview() {
    return this.auth.apiRequest('/graph/overview');
  }

  // Entity and Relationship Management
  async getEntities(entityType = null, limit = 50) {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (entityType) params.append('entity_type', entityType);
    
    return this.auth.apiRequest(`/entities?${params}`);
  }

  async getRelationships(limit = 20) {
    return this.auth.apiRequest(`/relationships?limit=${limit}`);
  }

  // Health and Monitoring
  async getHealthStatus() {
    return this.auth.apiRequest('/health');
  }
}

// Export instances
export const authManager = new AuthManager();
export const adminAPI = new AdminAPI(authManager);
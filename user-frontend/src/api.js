// API configuration
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class ApiClient {
  constructor() {
    this.baseURL = API_BASE_URL;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    try {
      console.log(`API Request: ${config.method || 'GET'} ${url}`);
      const response = await fetch(url, config);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      console.log(`API Response:`, data);
      return data;
    } catch (error) {
      console.error(`API Error for ${endpoint}:`, error);
      throw error;
    }
  }

  async get(endpoint) {
    return this.request(endpoint, { method: 'GET' });
  }

  async post(endpoint, data) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async postFormData(endpoint, formData) {
    return this.request(endpoint, {
      method: 'POST',
      headers: {}, // Don't set Content-Type for FormData
      body: formData,
    });
  }
}

export const apiClient = new ApiClient();

// API methods
export const api = {
  health: () => apiClient.get('/health'),
  getEntities: (limit = 10) => apiClient.get(`/entities?limit=${limit}`),
  getRelationships: (limit = 10) => apiClient.get(`/relationships?limit=${limit}`),
  getGraphOverview: () => apiClient.get('/graph/overview'),
  getEntityGraph: (entityName, maxDepth = 2) => 
    apiClient.get(`/graph/entity/${encodeURIComponent(entityName)}?max_depth=${maxDepth}`),
  post: (endpoint, data) => apiClient.post(endpoint, data), // Add this line
  uploadDocument: (file, tenantId = 'default') => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('tenant_id', tenantId);
    return apiClient.postFormData('/upload', formData);
  }
};
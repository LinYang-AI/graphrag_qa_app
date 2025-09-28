// admin-frontend/src/components/Dashboard.js
import React, { useState, useEffect } from 'react';
import { 
  BarChart3, 
  Users, 
  FileText, 
  Network, 
  Shield, 
  Settings,
  LogOut,
  Bell,
  Activity
} from 'lucide-react';
import { authManager, adminAPI } from '../utils/auth';

// Navigation Component
const Navigation = ({ activeTab, setActiveTab, user, onLogout }) => {
  const navItems = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'documents', label: 'Documents', icon: FileText },
    { id: 'users', label: 'Users', icon: Users },
    { id: 'knowledge-graph', label: 'Knowledge Graph', icon: Network },
    { id: 'system', label: 'System', icon: Settings }
  ];

  return (
    <div className="bg-white shadow-sm border-r border-gray-200 w-64 flex-shrink-0">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center">
          <Shield className="h-8 w-8 text-purple-600" />
          <div className="ml-3">
            <h1 className="text-lg font-semibold text-gray-900">Admin Console</h1>
            <p className="text-sm text-gray-500">GraphRAG Assistant</p>
          </div>
        </div>
      </div>

      {/* Navigation Items */}
      <nav className="mt-6 px-3">
        <div className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full group flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                  activeTab === item.id
                    ? 'bg-purple-100 text-purple-900'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <Icon className="mr-3 h-5 w-5 flex-shrink-0" />
                {item.label}
              </button>
            );
          })}
        </div>
      </nav>

      {/* User Info & Logout */}
      <div className="absolute bottom-0 w-64 p-4 border-t border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <div className="h-8 w-8 bg-purple-600 rounded-full flex items-center justify-center">
              <span className="text-white text-sm font-medium">
                {user?.email?.charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="ml-3">
              <p className="text-sm font-medium text-gray-700">{user?.email}</p>
              <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
            </div>
          </div>
          <button
            onClick={onLogout}
            className="text-gray-400 hover:text-gray-600"
            title="Logout"
          >
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  );
};

// Main Dashboard Component
const Dashboard = ({ user, onLogout }) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [systemStats, setSystemStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [notifications, setNotifications] = useState([]);

  useEffect(() => {
    loadSystemStats();
  }, []);

  const loadSystemStats = async () => {
    try {
      setLoading(true);
      const stats = await adminAPI.getSystemStats();
      setSystemStats(stats.stats || {});
      
      // Check for system issues
      const alerts = [];
      if (stats.stats?.documents === 0) {
        alerts.push({ type: 'warning', message: 'No documents uploaded yet' });
      }
      if (stats.stats?.users === 1) {
        alerts.push({ type: 'info', message: 'Only admin user exists' });
      }
      setNotifications(alerts);
      
    } catch (error) {
      console.error('Failed to load system stats:', error);
      setNotifications([{ type: 'error', message: 'Failed to load system statistics' }]);
    } finally {
      setLoading(false);
    }
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return <OverviewTab stats={systemStats} loading={loading} />;
      case 'documents':
        return <DocumentsTab onStatsUpdate={loadSystemStats} />;
      case 'users':
        return <UsersTab onStatsUpdate={loadSystemStats} />;
      case 'knowledge-graph':
        return <KnowledgeGraphTab />;
      case 'system':
        return <SystemTab stats={systemStats} />;
      default:
        return <OverviewTab stats={systemStats} loading={loading} />;
    }
  };

  return (
    <div className="flex h-screen bg-gray-50">
      <Navigation 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        user={user} 
        onLogout={onLogout} 
      />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <header className="bg-white shadow-sm border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-gray-900 capitalize">
              {activeTab.replace('-', ' ')}
            </h2>
            
            <div className="flex items-center space-x-4">
              {/* Notifications */}
              {notifications.length > 0 && (
                <div className="relative">
                  <Bell className="h-6 w-6 text-gray-400" />
                  <span className="absolute -top-1 -right-1 h-3 w-3 bg-red-500 rounded-full"></span>
                </div>
              )}
              
              {/* Status Indicator */}
              <div className="flex items-center">
                <Activity className="h-4 w-4 text-green-500 mr-2" />
                <span className="text-sm text-gray-600">System Online</span>
              </div>
            </div>
          </div>
          
          {/* Notifications Bar */}
          {notifications.length > 0 && (
            <div className="mt-3 space-y-2">
              {notifications.map((notification, index) => (
                <div
                  key={index}
                  className={`p-3 rounded-md text-sm ${
                    notification.type === 'error' ? 'bg-red-50 text-red-700 border border-red-200' :
                    notification.type === 'warning' ? 'bg-yellow-50 text-yellow-700 border border-yellow-200' :
                    'bg-blue-50 text-blue-700 border border-blue-200'
                  }`}
                >
                  {notification.message}
                </div>
              ))}
            </div>
          )}
        </header>

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto p-6">
          {renderTabContent()}
        </main>
      </div>
    </div>
  );
};

// Overview Tab Component
const OverviewTab = ({ stats, loading }) => {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
      </div>
    );
  }

  const statCards = [
    { label: 'Documents', value: stats.documents || 0, icon: FileText, color: 'blue' },
    { label: 'Entities', value: stats.entities || 0, icon: Network, color: 'green' },
    { label: 'Users', value: stats.users || 0, icon: Users, color: 'purple' },
    { label: 'Relationships', value: stats.relationships || 0, icon: Activity, color: 'orange' }
  ];

  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((stat, index) => {
          const Icon = stat.icon;
          return (
            <div key={index} className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <div className={`p-3 rounded-md bg-${stat.color}-100`}>
                  <Icon className={`h-6 w-6 text-${stat.color}-600`} />
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">{stat.label}</p>
                  <p className="text-2xl font-semibold text-gray-900">{stat.value.toLocaleString()}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* System Health */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">System Health</h3>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Database Connection</span>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
              Connected
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Vector Store</span>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
              Active
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">NLP Pipeline</span>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
              Ready
            </span>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Quick Actions</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 text-left">
            <FileText className="h-8 w-8 text-blue-600 mb-2" />
            <p className="font-medium text-gray-900">Upload Documents</p>
            <p className="text-sm text-gray-500">Add new knowledge sources</p>
          </button>
          <button className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 text-left">
            <Users className="h-8 w-8 text-purple-600 mb-2" />
            <p className="font-medium text-gray-900">Manage Users</p>
            <p className="text-sm text-gray-500">Add or modify user accounts</p>
          </button>
          <button className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 text-left">
            <Network className="h-8 w-8 text-green-600 mb-2" />
            <p className="font-medium text-gray-900">View Graph</p>
            <p className="text-sm text-gray-500">Explore knowledge relationships</p>
          </button>
        </div>
      </div>
    </div>
  );
};

// Placeholder components for other tabs
const DocumentsTab = ({ onStatsUpdate }) => (
  <div className="bg-white rounded-lg shadow p-6">
    <h3 className="text-lg font-medium text-gray-900 mb-4">Document Management</h3>
    <p className="text-gray-600">Document management interface will be implemented here.</p>
  </div>
);

const UsersTab = ({ onStatsUpdate }) => (
  <div className="bg-white rounded-lg shadow p-6">
    <h3 className="text-lg font-medium text-gray-900 mb-4">User Management</h3>
    <p className="text-gray-600">User management interface will be implemented here.</p>
  </div>
);

const KnowledgeGraphTab = () => (
  <div className="bg-white rounded-lg shadow p-6">
    <h3 className="text-lg font-medium text-gray-900 mb-4">Knowledge Graph</h3>
    <p className="text-gray-600">Knowledge graph visualization will be implemented here.</p>
  </div>
);

const SystemTab = ({ stats }) => (
  <div className="space-y-6">
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">System Configuration</h3>
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="border border-gray-200 rounded-lg p-4">
            <h4 className="font-medium text-gray-900">Database Settings</h4>
            <p className="text-sm text-gray-600 mt-1">Neo4j Configuration</p>
            <div className="mt-2 space-y-1 text-xs text-gray-500">
              <div>Entities: {stats.entities || 0}</div>
              <div>Relationships: {stats.relationships || 0}</div>
              <div>Chunks: {stats.chunks || 0}</div>
            </div>
          </div>
          
          <div className="border border-gray-200 rounded-lg p-4">
            <h4 className="font-medium text-gray-900">Vector Store</h4>
            <p className="text-sm text-gray-600 mt-1">Weaviate Configuration</p>
            <div className="mt-2 space-y-1 text-xs text-gray-500">
              <div>Embeddings: {stats.vector_embeddings || 0}</div>
              <div>Dimensions: 384</div>
              <div>Model: all-MiniLM-L6-v2</div>
            </div>
          </div>
        </div>
        
        <div className="border border-gray-200 rounded-lg p-4">
          <h4 className="font-medium text-gray-900">System Logs</h4>
          <p className="text-sm text-gray-600 mt-1">Recent system activity</p>
          <div className="mt-3 text-xs font-mono bg-gray-50 p-3 rounded">
            <div>2024-01-01 12:00:00 - System started successfully</div>
            <div>2024-01-01 12:00:05 - Neo4j connected</div>
            <div>2024-01-01 12:00:10 - Weaviate connected</div>
            <div>2024-01-01 12:00:15 - Sample documents processed</div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

export default Dashboard;
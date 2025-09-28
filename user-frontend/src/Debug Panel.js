import React, { useState, useEffect } from 'react';
import { AlertCircle, Database, Network } from 'lucide-react';

const DebugPanel = () => {
  const [debugData, setDebugData] = useState({
    entities: [],
    relationships: [],
    overview: {},
    apiStatus: 'checking...'
  });
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (isVisible) {
      loadDebugData();
    }
  }, [isVisible]);

  const loadDebugData = async () => {
    try {
      // Test API connectivity
      const healthResponse = await fetch('/health');
      const healthData = await healthResponse.json();
      console.log('Health check:', healthData);

      // Load entities
      const entitiesResponse = await fetch('/entities?limit=10');
      const entitiesData = await entitiesResponse.json();
      console.log('Entities response:', entitiesData);

      // Load relationships
      const relResponse = await fetch('/relationships?limit=10');
      const relData = await relResponse.json();
      console.log('Relationships response:', relData);

      // Load overview
      const overviewResponse = await fetch('/graph/overview');
      const overviewData = await overviewResponse.json();
      console.log('Overview response:', overviewData);

      setDebugData({
        entities: entitiesData.entities || [],
        relationships: relData.relationships || [],
        overview: overviewData.graph_stats || {},
        apiStatus: 'connected'
      });

    } catch (error) {
      console.error('Debug data loading error:', error);
      setDebugData(prev => ({
        ...prev,
        apiStatus: `Error: ${error.message}`
      }));
    }
  };

  if (!isVisible) {
    return (
      <button
        onClick={() => setIsVisible(true)}
        className="fixed bottom-4 right-4 bg-red-600 text-white p-3 rounded-full shadow-lg hover:bg-red-700"
        title="Show Debug Panel"
      >
        <AlertCircle size={20} />
      </button>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 w-96 bg-white border-2 border-red-200 rounded-lg shadow-xl z-50">
      <div className="bg-red-600 text-white p-3 rounded-t-lg flex justify-between items-center">
        <h3 className="font-semibold">Debug Panel</h3>
        <button
          onClick={() => setIsVisible(false)}
          className="text-white hover:text-gray-200"
        >
          ✕
        </button>
      </div>
      
      <div className="p-4 max-h-96 overflow-y-auto text-sm">
        {/* API Status */}
        <div className="mb-4">
          <div className="flex items-center mb-2">
            <Network size={16} className="mr-2" />
            <strong>API Status:</strong>
          </div>
          <div className={`p-2 rounded ${debugData.apiStatus === 'connected' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            {debugData.apiStatus}
          </div>
        </div>

        {/* Graph Stats */}
        <div className="mb-4">
          <div className="flex items-center mb-2">
            <Database size={16} className="mr-2" />
            <strong>Graph Stats:</strong>
          </div>
          <div className="bg-gray-100 p-2 rounded">
            <div>Documents: {debugData.overview.documents || 0}</div>
            <div>Entities: {debugData.overview.entities || 0}</div>
            <div>Relationships: {debugData.overview.relationships || 0}</div>
            <div>Chunks: {debugData.overview.chunks || 0}</div>
          </div>
        </div>

        {/* Sample Entities */}
        <div className="mb-4">
          <strong>Sample Entities:</strong>
          <div className="bg-gray-100 p-2 rounded mt-1 max-h-32 overflow-y-auto">
            {debugData.entities.length > 0 ? (
              debugData.entities.map((entity, idx) => (
                <div key={idx} className="text-xs">
                  {entity.name} ({entity.type}) - {entity.mentions} mentions
                </div>
              ))
            ) : (
              <div className="text-red-600">No entities found</div>
            )}
          </div>
        </div>

        {/* Sample Relationships */}
        <div className="mb-4">
          <strong>Sample Relationships:</strong>
          <div className="bg-gray-100 p-2 rounded mt-1 max-h-32 overflow-y-auto">
            {debugData.relationships.length > 0 ? (
              debugData.relationships.map((rel, idx) => (
                <div key={idx} className="text-xs">
                  {rel.source} → {rel.target} ({rel.relationship})
                </div>
              ))
            ) : (
              <div className="text-red-600">No relationships found</div>
            )}
          </div>
        </div>

        {/* Refresh Button */}
        <button
          onClick={loadDebugData}
          className="w-full bg-blue-600 text-white p-2 rounded hover:bg-blue-700"
        >
          Refresh Debug Data
        </button>
      </div>
    </div>
  );
};

export default DebugPanel;
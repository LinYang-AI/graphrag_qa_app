import React, { useEffect, useRef, useState, useCallback } from 'react';
import cytoscape from 'cytoscape';
import dagre from 'cytoscape-dagre';
import coseBilkent from 'cytoscape-cose-bilkent';
import { Search, Filter, RotateCcw, Download, AlertTriangle, AlertCircle, Database, Network } from 'lucide-react';
import { api } from './api';

// Register Cytoscape extensions
cytoscape.use(dagre);
cytoscape.use(coseBilkent);

// Debug Panel Component
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
      const healthData = await api.health();
      console.log('Health check:', healthData);

      // Load entities
      const entitiesData = await api.getEntities(10);
      console.log('Entities response:', entitiesData);

      // Load relationships
      const relData = await api.getRelationships(10);
      console.log('Relationships response:', relData);

      // Load overview
      const overviewData = await api.getGraphOverview();
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
        className="fixed bottom-4 right-4 bg-red-600 text-white p-3 rounded-full shadow-lg hover:bg-red-700 z-50"
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

// Main Graph Visualization Component
const GraphVisualization = () => {
  const cyRef = useRef(null);
  const [cy, setCy] = useState(null);
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [selectedEntity, setSelectedEntity] = useState(null);
  const [filters, setFilters] = useState({
    entityTypes: ['PERSON', 'ORG', 'GPE', 'MONEY'],
    minConfidence: 0.3,
    maxNodes: 50
  });
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [graphStats, setGraphStats] = useState({});
  const [error, setError] = useState(null);
  const [apiConnected, setApiConnected] = useState(false);

  // Color scheme for different entity types
  const entityColors = {
    PERSON: '#3B82F6',  // Blue
    ORG: '#10B981',     // Green
    GPE: '#F59E0B',     // Yellow
    MONEY: '#EF4444',   // Red
    PRODUCT: '#8B5CF6', // Purple
    EVENT: '#F97316',   // Orange
    default: '#6B7280'  // Gray
  };

  // Memoize the update graph function to fix dependency issues
  const updateGraph = useCallback(() => {
    if (!cy) return;

    console.log('Updating graph with data:', graphData);

    // Filter nodes based on current filters
    const filteredNodes = graphData.nodes.filter(node => 
      filters.entityTypes.includes(node.data.type) &&
      (searchTerm === '' || node.data.label.toLowerCase().includes(searchTerm.toLowerCase()))
    );

    // Filter edges to only include connections between visible nodes
    const nodeIds = new Set(filteredNodes.map(n => n.data.id));
    const filteredEdges = graphData.edges.filter(edge =>
      nodeIds.has(edge.data.source) && 
      nodeIds.has(edge.data.target) &&
      edge.data.confidence >= filters.minConfidence
    );

    console.log('Filtered nodes:', filteredNodes.length);
    console.log('Filtered edges:', filteredEdges.length);

    // Update graph
    cy.elements().remove();
    cy.add([...filteredNodes, ...filteredEdges]);
    
    // Apply layout
    cy.layout({
      name: 'cose-bilkent',
      animate: true,
      animationDuration: 1000
    }).run();
  }, [cy, graphData, filters, searchTerm]);

  // Memoize loadGraphOverview to fix dependency issues
  const loadGraphOverview = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      console.log('Loading graph overview...');
      
      // Test API connection first
      const healthData = await api.health();
      console.log('Health check response:', healthData);
      setApiConnected(true);
      
      const data = await api.getGraphOverview();
      console.log('Graph overview response:', data);
      
      if (data.status === 'success') {
        setGraphStats(data.graph_stats);
        
        // Load entities for the overview graph
        console.log('Loading entities...');
        const entitiesData = await api.getEntities(filters.maxNodes);
        console.log('Entities response:', entitiesData);
        
        if (entitiesData.status === 'success' && entitiesData.entities.length > 0) {
          await buildGraphFromEntities(entitiesData.entities);
        } else {
          setError('No entities found. Please upload some documents first.');
        }
      } else {
        setError(`Graph overview failed: ${data.message || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error loading graph overview:', error);
      setError(`Failed to load graph: ${error.message}`);
      setApiConnected(false);
    } finally {
      setIsLoading(false);
    }
  };

  // Initialize Cytoscape
  useEffect(() => {
    if (cyRef.current && !cy) {
      const cytoscapeInstance = cytoscape({
        container: cyRef.current,
        style: [
          {
            selector: 'node',
            style: {
              'background-color': (ele) => entityColors[ele.data('type')] || entityColors.default,
              'label': 'data(label)',
              'color': '#FFFFFF',
              'text-valign': 'center',
              'text-halign': 'center',
              'font-size': '12px',
              'font-weight': 'bold',
              'width': (ele) => Math.max(30, (ele.data('mentions') || 1) * 10),
              'height': (ele) => Math.max(30, (ele.data('mentions') || 1) * 10),
              'border-width': 2,
              'border-color': '#FFFFFF',
              'text-wrap': 'wrap',
              'text-max-width': '100px'
            }
          },
          {
            selector: 'node:selected',
            style: {
              'border-width': 4,
              'border-color': '#FCD34D'
            }
          },
          {
            selector: 'edge',
            style: {
              'width': (ele) => Math.max(2, (ele.data('confidence') || 0.5) * 5),
              'line-color': (ele) => {
                const relType = ele.data('relationship');
                if (relType === 'WORKS_FOR') return '#3B82F6';
                if (relType === 'FOUNDED') return '#10B981';
                if (relType === 'PARTNERS_WITH') return '#F59E0B';
                if (relType === 'CO_MENTIONED') return '#D1D5DB';
                return '#6B7280';
              },
              'target-arrow-color': '#6B7280',
              'target-arrow-shape': 'triangle',
              'curve-style': 'bezier',
              'label': 'data(relationship)',
              'font-size': '10px',
              'text-rotation': 'autorotate',
              'text-margin-y': -10
            }
          },
          {
            selector: 'edge:selected',
            style: {
              'line-color': '#FCD34D',
              'width': 4
            }
          }
        ],
        layout: {
          name: 'cose-bilkent',
          animate: true,
          animationDuration: 1000,
          nodeRepulsion: 4500,
          idealEdgeLength: 100,
          edgeElasticity: 0.45
        }
      });

      // Event handlers
      cytoscapeInstance.on('tap', 'node', (evt) => {
        const node = evt.target;
        const entityName = node.data('id');
        handleNodeClick(entityName);
      });

      cytoscapeInstance.on('tap', 'edge', (evt) => {
        const edge = evt.target;
        console.log('Edge clicked:', edge.data());
      });

      setCy(cytoscapeInstance);
    }

    return () => {
      if (cy) {
        cy.destroy();
      }
    };
  }, []); // Empty dependency array is correct here

  // Load initial graph data
  useEffect(() => {
    loadGraphOverview();
  }, [loadGraphOverview]);

  // Update graph when data changes
  useEffect(() => {
    if (cy && graphData.nodes.length > 0) {
      updateGraph();
    }
  }, [cy, graphData, updateGraph]);

  // const loadGraphOverview = async () => {
  //   setIsLoading(true);
  //   setError(null);
    
  //   try {
  //     console.log('Loading graph overview...');
      
  //     // Test API connection first
  //     const healthData = await api.health();
  //     console.log('Health check response:', healthData);
  //     setApiConnected(true);
      
  //     const data = await api.getGraphOverview();
  //     console.log('Graph overview response:', data);
      
  //     if (data.status === 'success') {
  //       setGraphStats(data.graph_stats);
        
  //       // Load entities for the overview graph
  //       console.log('Loading entities...');
  //       const entitiesData = await api.getEntities(filters.maxNodes);
  //       console.log('Entities response:', entitiesData);
        
  //       if (entitiesData.status === 'success' && entitiesData.entities.length > 0) {
  //         await buildGraphFromEntities(entitiesData.entities);
  //       } else {
  //         setError('No entities found. Please upload some documents first.');
  //       }
  //     } else {
  //       setError(`Graph overview failed: ${data.message || 'Unknown error'}`);
  //     }
  //   } catch (error) {
  //     console.error('Error loading graph overview:', error);
  //     setError(`Failed to load graph: ${error.message}`);
  //     setApiConnected(false);
  //   } finally {
  //     setIsLoading(false);
  //   }
  // };

  const buildGraphFromEntities = async (entities) => {
    console.log('Building graph from entities:', entities);
    
    if (!entities || entities.length === 0) {
      setError('No entities to display');
      return;
    }
    
    // Create nodes from entities
    const nodes = entities.map(entity => {
      if (!entity.name) {
        console.warn('Entity without name:', entity);
        return null;
      }
      
      return {
        data: {
          id: entity.name,
          label: entity.name,
          type: entity.type || 'UNKNOWN',
          mentions: entity.mentions || 1
        }
      };
    }).filter(node => node !== null);

    console.log('Created nodes:', nodes);

    // Load relationships
    try {
      console.log('Loading relationships...');
      const relData = await api.getRelationships(100);
      console.log('Relationships response:', relData);
      
      const edges = relData.status === 'success' && relData.relationships ? 
        relData.relationships.map(rel => ({
          data: {
            id: `${rel.source}-${rel.target}`,
            source: rel.source,
            target: rel.target,
            relationship: rel.relationship || 'RELATED',
            confidence: rel.confidence || 0.5
          }
        })) : [];

      console.log('Created edges:', edges);
      setGraphData({ nodes, edges });
      
      if (nodes.length === 0 && edges.length === 0) {
        setError('No graph data to display. Try uploading documents with clear entity relationships.');
      }
      
    } catch (error) {
      console.error('Error loading relationships:', error);
      setGraphData({ nodes, edges: [] });
    }
  };

  // const updateGraph = () => {
  //   if (!cy) return;

  //   console.log('Updating graph with data:', graphData);

  //   // Filter nodes based on current filters
  //   const filteredNodes = graphData.nodes.filter(node => 
  //     filters.entityTypes.includes(node.data.type) &&
  //     (searchTerm === '' || node.data.label.toLowerCase().includes(searchTerm.toLowerCase()))
  //   );

  //   // Filter edges to only include connections between visible nodes
  //   const nodeIds = new Set(filteredNodes.map(n => n.data.id));
  //   const filteredEdges = graphData.edges.filter(edge =>
  //     nodeIds.has(edge.data.source) && 
  //     nodeIds.has(edge.data.target) &&
  //     edge.data.confidence >= filters.minConfidence
  //   );

  //   console.log('Filtered nodes:', filteredNodes.length);
  //   console.log('Filtered edges:', filteredEdges.length);

  //   // Update graph
  //   cy.elements().remove();
  //   cy.add([...filteredNodes, ...filteredEdges]);
    
  //   // Apply layout
  //   cy.layout({
  //     name: 'cose-bilkent',
  //     animate: true,
  //     animationDuration: 1000
  //   }).run();
  // };

  const handleNodeClick = async (entityName) => {
    setSelectedEntity(entityName);
    
    // Load entity neighborhood
    try {
      const response = await fetch(`/graph/entity/${encodeURIComponent(entityName)}?max_depth=2`);
      const data = await response.json();
      
      if (data.status === 'success' && data.graph.nodes.length > 0) {
        // Build graph from entity neighborhood
        const nodes = data.graph.nodes.map(node => ({
          data: {
            id: node.name,
            label: node.name,
            type: node.type,
            mentions: 1
          }
        }));

        const edges = data.graph.edges.map(edge => ({
          data: {
            id: `${edge.source}-${edge.target}`,
            source: edge.source,
            target: edge.target,
            relationship: edge.relationship,
            confidence: edge.confidence
          }
        }));

        setGraphData({ nodes, edges });
      }
    } catch (error) {
      console.error('Error loading entity neighborhood:', error);
    }
  };

  const handleSearch = async () => {
    if (!searchTerm) {
      loadGraphOverview();
      return;
    }

    setIsLoading(true);
    try {
      // Search for entities matching the term
      const data = await api.getEntities(20);
      
      if (data.status === 'success') {
        const matchingEntities = data.entities.filter(entity =>
          entity.name && entity.name.toLowerCase().includes(searchTerm.toLowerCase())
        );
        
        if (matchingEntities.length > 0) {
          buildGraphFromEntities(matchingEntities);
        } else {
          setError(`No entities found matching "${searchTerm}"`);
        }
      }
    } catch (error) {
      console.error('Error searching entities:', error);
      setError(`Search failed: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const resetGraph = () => {
    setSearchTerm('');
    setSelectedEntity(null);
    setError(null);
    loadGraphOverview();
  };

  const exportGraph = () => {
    if (cy) {
      const png = cy.png({ scale: 2, full: true });
      const link = document.createElement('a');
      link.download = 'knowledge-graph.png';
      link.href = png;
      link.click();
    }
  };

  return (
    <div className="flex h-screen bg-gray-100 min-h-0">
      {/* Sidebar */}
      <div className="w-80 min-w-80 bg-white shadow-lg flex flex-col">
        <div className="p-6 flex-1 overflow-y-auto">
          <h2 className="text-2xl font-bold mb-6 text-gray-800">Knowledge Graph</h2>
        
        {/* Search */}
        <div className="mb-6">
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Search entities..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md"
            />
            <button
              onClick={handleSearch}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              <Search size={16} />
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <h3 className="font-semibold mb-2">Graph Statistics</h3>
          <div className="space-y-1 text-sm">
            <div>Documents: {graphStats.documents || 0}</div>
            <div>Entities: {graphStats.entities || 0}</div>
            <div>Relationships: {graphStats.relationships || 0}</div>
            <div>Chunks: {graphStats.chunks || 0}</div>
          </div>
        </div>

        {/* Filters */}
        <div className="mb-6">
          <h3 className="font-semibold mb-3">Filters</h3>
          
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2">Entity Types</label>
            <div className="space-y-2">
              {Object.keys(entityColors).filter(key => key !== 'default').map(type => (
                <label key={type} className="flex items-center">
                  <input
                    type="checkbox"
                    checked={filters.entityTypes.includes(type)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setFilters(prev => ({
                          ...prev,
                          entityTypes: [...prev.entityTypes, type]
                        }));
                      } else {
                        setFilters(prev => ({
                          ...prev,
                          entityTypes: prev.entityTypes.filter(t => t !== type)
                        }));
                      }
                    }}
                    className="mr-2"
                  />
                  <span 
                    className="w-4 h-4 rounded mr-2"
                    style={{ backgroundColor: entityColors[type] }}
                  ></span>
                  <span className="text-sm">{type}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium mb-2">
              Min Confidence: {filters.minConfidence}
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={filters.minConfidence}
              onChange={(e) => setFilters(prev => ({ ...prev, minConfidence: parseFloat(e.target.value) }))}
              className="w-full"
            />
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium mb-2">
              Max Nodes: {filters.maxNodes}
            </label>
            <input
              type="range"
              min="10"
              max="100"
              step="10"
              value={filters.maxNodes}
              onChange={(e) => setFilters(prev => ({ ...prev, maxNodes: parseInt(e.target.value) }))}
              className="w-full"
            />
          </div>

          <button
            onClick={updateGraph}
            className="w-full px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
          >
            <Filter className="inline mr-2" size={16} />
            Apply Filters
          </button>
        </div>

        {/* Controls */}
        <div className="space-y-2">
          <button
            onClick={resetGraph}
            className="w-full px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
          >
            <RotateCcw className="inline mr-2" size={16} />
            Reset View
          </button>
          
          <button
            onClick={exportGraph}
            className="w-full px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700"
          >
            <Download className="inline mr-2" size={16} />
            Export PNG
          </button>
        </div>

        {/* Selected Entity Info */}
        {selectedEntity && (
          <div className="mt-6 p-4 bg-blue-50 rounded-lg">
            <h3 className="font-semibold mb-2">Selected Entity</h3>
            <div className="text-sm">
              <div><strong>Name:</strong> {selectedEntity}</div>
              <div className="mt-2 text-xs text-gray-600">
                Click nodes to explore their neighborhood
              </div>
            </div>
          </div>
        )}
        </div>
      </div>

      {/* Main Graph Area */}
      <div className="flex-1 relative">
        {/* Error Display */}
        {error && (
          <div className="absolute top-4 left-4 right-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded z-10">
            <div className="flex">
              <AlertTriangle className="flex-shrink-0 mr-2" size={20} />
              <div>
                <strong>Error:</strong> {error}
              </div>
            </div>
          </div>
        )}
        
        {/* API Status */}
        {!apiConnected && (
          <div className="absolute top-16 left-4 right-4 bg-yellow-100 border border-yellow-400 text-yellow-700 px-4 py-3 rounded z-10">
            <div className="flex">
              <AlertTriangle className="flex-shrink-0 mr-2" size={20} />
              <div>
                API not connected. Make sure the backend is running on port 8000.
              </div>
            </div>
          </div>
        )}
        
        {isLoading && (
          <div className="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center z-10">
            <div className="text-lg">Loading graph...</div>
          </div>
        )}
        
        <div 
          ref={cyRef} 
          className="w-full h-full"
          style={{ background: '#f8fafc' }}
        />
        
        {/* Graph Legend */}
        <div className="absolute top-4 right-4 bg-white p-4 rounded-lg shadow-lg">
          <h4 className="font-semibold mb-2">Legend</h4>
          <div className="space-y-1 text-sm">
            {Object.entries(entityColors).filter(([key]) => key !== 'default').map(([type, color]) => (
              <div key={type} className="flex items-center">
                <div 
                  className="w-3 h-3 rounded mr-2"
                  style={{ backgroundColor: color }}
                ></div>
                <span>{type}</span>
              </div>
            ))}
          </div>
          <div className="mt-2 text-xs text-gray-600">
            • Node size = mention frequency<br/>
            • Edge width = confidence level
          </div>
        </div>
      </div>
      
      {/* Debug Panel */}
      <DebugPanel />
    </div>
  );
};

export default GraphVisualization;
import React, { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import dagre from 'cytoscape-dagre';
import { Maximize2, Minimize2, RotateCcw, Settings } from 'lucide-react';
import { api } from './api';

// Register Cytoscape extensions
cytoscape.use(dagre);

const GraphWidget = () => {
  const cyRef = useRef(null);
  const [cy, setCy] = useState(null);
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [isExpanded, setIsExpanded] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [widgetSettings, setWidgetSettings] = useState({
    maxNodes: 30,
    showLabels: true,
    layoutType: 'dagre'
  });

  // Color scheme for entities
  const entityColors = {
    PERSON: '#3B82F6',
    ORG: '#10B981',
    GPE: '#F59E0B',
    MONEY: '#EF4444',
    PRODUCT: '#8B5CF6',
    EVENT: '#F97316',
    default: '#6B7280'
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
              'label': (ele) => widgetSettings.showLabels ? ele.data('label') : '',
              'color': '#FFFFFF',
              'text-valign': 'center',
              'text-halign': 'center',
              'font-size': '10px',
              'font-weight': 'bold',
              'width': '20px',
              'height': '20px',
              'border-width': 1,
              'border-color': '#FFFFFF',
              'text-max-width': '60px',
              'text-wrap': 'wrap'
            }
          },
          {
            selector: 'node:selected',
            style: {
              'border-width': 2,
              'border-color': '#FCD34D'
            }
          },
          {
            selector: 'edge',
            style: {
              'width': 1,
              'line-color': '#9CA3AF',
              'target-arrow-color': '#9CA3AF',
              'target-arrow-shape': 'triangle',
              'target-arrow-size': '6px',
              'curve-style': 'haystack',
              'opacity': 0.6
            }
          }
        ],
        
        layout: {
          name: widgetSettings.layoutType,
          directed: true,
          padding: 10
        }
      });

      setCy(cytoscapeInstance);
    }

    return () => {
      if (cy) {
        cy.destroy();
        setCy(null);
      }
    };
  }, [widgetSettings.showLabels, widgetSettings.layoutType]);

  // Load graph data
  useEffect(() => {
    loadGraphData();
  }, [widgetSettings.maxNodes]);

  const loadGraphData = async () => {
    setIsLoading(true);
    try {
      console.log('Loading graph data for widget...');
      
      const entitiesData = await api.getEntities(widgetSettings.maxNodes);
      
      if (entitiesData.status === 'success' && entitiesData.entities) {
        const nodes = entitiesData.entities
          .filter(entity => entity.name && entity.name.trim() !== '')
          .map(entity => ({
            data: {
              id: entity.name,
              label: entity.name,
              type: entity.type || 'UNKNOWN'
            }
          }));

        console.log('Widget nodes:', nodes);

        const relData = await api.getRelationships(50);
        console.log('Widget relationships:', relData);
        
        // Filter edges to only include connections between existing nodes
        const nodeIds = new Set(nodes.map(n => n.data.id));
        
        const edges = relData.status === 'success' && relData.relationships ?
          relData.relationships
            .filter(rel => 
              rel.source && rel.target && 
              nodeIds.has(rel.source) && nodeIds.has(rel.target) &&
              rel.source !== rel.target
            )
            .map(rel => ({
              data: {
                id: `${rel.source}-${rel.target}`,
                source: rel.source,
                target: rel.target,
                relationship: rel.relationship || 'RELATED'
              }
            })) : [];

        console.log('Widget filtered edges:', edges);

        setGraphData({ nodes, edges });
      } else {
        console.warn('No entities data received');
        setGraphData({ nodes: [], edges: [] });
      }
    } catch (error) {
      console.error('Error loading graph data:', error);
      setGraphData({ nodes: [], edges: [] });
    } finally {
      setIsLoading(false);
    }
  };

  // Update graph when data changes
  useEffect(() => {
    if (cy && !isLoading) {
      updateGraphVisualization();
    }
  }, [cy, graphData, isLoading]);

  const updateGraphVisualization = () => {
    if (!cy || isLoading) return;

    try {
      console.log('Updating widget graph visualization...');
      
      // Clear existing elements
      cy.elements().remove();
      
      // Add nodes first
      if (graphData.nodes.length > 0) {
        cy.add(graphData.nodes);
        console.log(`Added ${graphData.nodes.length} nodes`);
      }
      
      // Add edges only if both source and target nodes exist
      const validEdges = graphData.edges.filter(edge => {
        const sourceExists = cy.$(`node[id="${edge.data.source}"]`).length > 0;
        const targetExists = cy.$(`node[id="${edge.data.target}"]`).length > 0;
        return sourceExists && targetExists;
      });
      
      if (validEdges.length > 0) {
        cy.add(validEdges);
        console.log(`Added ${validEdges.length} valid edges of ${graphData.edges.length} total`);
      }
      
      // Apply layout
      cy.layout({
        name: widgetSettings.layoutType,
        directed: true,
        padding: 10,
        animate: false
      }).run();

    } catch (error) {
      console.error('Error updating graph visualization:', error);
    }
  };

  const resetView = () => {
    if (cy) {
      cy.fit();
      cy.center();
    }
  };

  const handleRefreshGraph = () => {
    loadGraphData();
  };

  return (
    <div className={`flex flex-col h-full ${isExpanded ? 'fixed inset-0 z-50 bg-white' : ''}`}>
      {/* Widget Header */}
      <div className="p-4 border-b bg-white">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Knowledge Graph</h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="p-1 text-gray-500 hover:text-gray-700"
              title="Settings"
            >
              <Settings size={16} />
            </button>
            <button
              onClick={resetView}
              className="p-1 text-gray-500 hover:text-gray-700"
              title="Reset View"
            >
              <RotateCcw size={16} />
            </button>
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1 text-gray-500 hover:text-gray-700"
              title={isExpanded ? "Minimize" : "Expand"}
            >
              {isExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            </button>
          </div>
        </div>

        {/* Widget Settings */}
        {showSettings && (
          <div className="mt-3 p-3 bg-gray-50 rounded-lg">
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Max Nodes: {widgetSettings.maxNodes}
                </label>
                <input
                  type="range"
                  min="10"
                  max="50"
                  value={widgetSettings.maxNodes}
                  onChange={(e) => setWidgetSettings(prev => ({ 
                    ...prev, 
                    maxNodes: parseInt(e.target.value) 
                  }))}
                  className="w-full"
                />
              </div>
              
              <div>
                <label className="flex items-center text-xs">
                  <input
                    type="checkbox"
                    checked={widgetSettings.showLabels}
                    onChange={(e) => setWidgetSettings(prev => ({ 
                      ...prev, 
                      showLabels: e.target.checked 
                    }))}
                    className="mr-2"
                  />
                  Show Labels
                </label>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Layout</label>
                <select
                  value={widgetSettings.layoutType}
                  onChange={(e) => setWidgetSettings(prev => ({ 
                    ...prev, 
                    layoutType: e.target.value 
                  }))}
                  className="w-full text-xs border rounded px-2 py-1"
                >
                  <option value="dagre">Hierarchical</option>
                  <option value="circle">Circle</option>
                  <option value="grid">Grid</option>
                </select>
              </div>

              <button
                onClick={handleRefreshGraph}
                disabled={isLoading}
                className="w-full px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {isLoading ? 'Loading...' : 'Refresh Graph'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Graph Area */}
      <div className="flex-1 relative">
        {isLoading && (
          <div className="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center z-10">
            <div className="text-sm text-gray-600">Loading graph...</div>
          </div>
        )}
        
        <div 
          ref={cyRef}
          className="w-full h-full"
          style={{ background: '#f8fafc' }}
        />

        {/* Graph Stats */}
        <div className="absolute bottom-2 left-2 bg-white bg-opacity-90 px-2 py-1 rounded text-xs">
          <div>Nodes: {graphData.nodes.length}</div>
          <div>Edges: {graphData.edges.length}</div>
        </div>

        {/* Error Prevention Info */}
        {graphData.nodes.length === 0 && !isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-gray-500">
              <div className="text-sm">No graph data available</div>
              <button
                onClick={handleRefreshGraph}
                className="mt-2 text-xs text-blue-600 hover:text-blue-800"
              >
                Try refreshing
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default GraphWidget;
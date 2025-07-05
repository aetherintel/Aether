import { useEffect, useRef, useState } from 'react';
import { Card, Button, Select, Stack, Group, Text, Loader } from '@mantine/core';
import { authFetch } from '@/utils/authFetch';

interface GraphVisualizationProps {
  selectedChannelIds: string[];
  searchQuery?: string;
}

const GraphVisualization: React.FC<GraphVisualizationProps> = ({ 
  selectedChannelIds, 
  searchQuery 
}) => {
  const vizRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<any>(null);
  const [loading, setLoading] = useState(false);
  const [visualizationType, setVisualizationType] = useState<string>('network');
  const [visLoaded, setVisLoaded] = useState(false);

  // Load vis.js from CDN 
  // TODO: install npm packages vis-network and vis-data
  useEffect(() => {
    const loadVis = () => {
      if ((window as any).vis) {
        setVisLoaded(true);
        return;
      }

      const script = document.createElement('script');
      script.src = 'https://unpkg.com/vis-network/standalone/umd/vis-network.min.js';
      script.onload = () => {
        setVisLoaded(true);
      };
      script.onerror = () => {
        console.error('Failed to load vis.js');
      };
      document.head.appendChild(script);
    };

    loadVis();
  }, []);

  const renderNetworkVisualization = async (data: any) => {
    if (!visLoaded || !vizRef.current) {return;}

    // Clear previous visualization
    if (networkRef.current) {
      networkRef.current.destroy();
      networkRef.current = null;
    }

    // Prepare nodes
    const nodes = data.nodes.map((node: any) => ({
      id: node.id,
      label: node.label,
      group: node.type,
      title: `${node.type}: ${node.label}`,
      color: {
        background: node.type === 'Channel' ? '#ff6b6b' : '#4ecdc4',
        border: node.type === 'Channel' ? '#ff5252' : '#26c6da',
        highlight: {
          background: node.type === 'Channel' ? '#ff8a80' : '#80e5ff',
          border: node.type === 'Channel' ? '#ff1744' : '#00acc1'
        }
      },
      size: Math.max((node.properties?.message_count || 1) * 2, 15),
      font: { size: 12, color: '#000000' }
    }));

    // Prepare edges
    const edges = data.relationships.map((rel: any) => ({
      id: rel.id,
      from: rel.from,
      to: rel.to,
      label: rel.type,
      title: `${rel.type}${rel.properties?.message_count ? ` (${rel.properties.message_count} messages)` : ''}`,
      width: Math.min(Math.max(rel.properties?.message_count || 1, 1), 10),
      arrows: 'to',
      color: { 
        color: '#848484',
        highlight: '#2196f3',
        hover: '#2196f3'
      },
      smooth: { type: 'continuous' }
    }));

    // Create datasets
    const nodeDataset = new (window as any).vis.DataSet(nodes);
    const edgeDataset = new (window as any).vis.DataSet(edges);

    // Network options
    const options = {
      nodes: {
        shape: 'dot',
        scaling: {
          min: 10,
          max: 30,
        },
        font: {
          size: 12,
          face: 'Tahoma'
        },
      },
      edges: {
        width: 0.15,
        color: { inherit: 'from' },
        smooth: {
          type: 'continuous'
        }
      },
      physics: {
        enabled: true,
        barnesHut: {
          gravitationalConstant: -8000,
          centralGravity: 0.3,
          springLength: 95,
          springConstant: 0.04,
          damping: 0.09
        },
        maxVelocity: 50,
        minVelocity: 0.1,
        solver: 'barnesHut',
        stabilization: { iterations: 80 },
        timestep: 0.35,
        adaptiveTimestep: true
      },
      interaction: {
        tooltipDelay: 200,
        hideEdgesOnDrag: true,
        hideNodesOnDrag: false
      }
    };

    // Create network
    networkRef.current = new (window as any).vis.Network(
      vizRef.current,
      { nodes: nodeDataset, edges: edgeDataset },
      options
    );

    // Add event listeners
    networkRef.current.on('click', (params: any) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        const node = nodes.find((n: { id: any; }) => n.id === nodeId);
        console.log('Clicked node:', node);
      }
    });
  };

  const renderVisualization = async () => {
    if (!vizRef.current) {return;}

    setLoading(true);
    
    try {
      // Fetch data from our backend endpoint
      const response = await authFetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000/api'}/graph/visualization`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          channel_ids: selectedChannelIds,
          search_query: searchQuery,
          limit: 100,
          visualization_type: visualizationType
        })
      });

      const data = await response.json();

      if (visualizationType === 'network') {
        await renderNetworkVisualization(data);
      } else if (visualizationType === 'timeline') {
        renderTimelineVisualization(data);
      }

    } catch (error) {
      console.error('Error rendering visualization:', error);
    } finally {
      setLoading(false);
    }
  };

  const renderTimelineVisualization = (data: any) => {
    if (!vizRef.current) {return;}

    // Clear previous network
    if (networkRef.current) {
      networkRef.current.destroy();
      networkRef.current = null;
    }

    // Clear previous content
    vizRef.current.innerHTML = '';

    // Create timeline HTML
    const timelineContainer = document.createElement('div');
    timelineContainer.style.cssText = `
      height: 400px;
      overflow-y: auto;
      padding: 20px;
      background: #f8f9fa;
      border-radius: 8px;
    `;

    data.timeline.forEach((item: any) => {
      const timelineItem = document.createElement('div');
      timelineItem.style.cssText = `
        display: flex;
        margin-bottom: 20px;
        padding: 15px;
        background: white;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #3b82f6;
      `;

      timelineItem.innerHTML = `
        <div style="flex: 1;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <strong style="color: #1f2937;">${item.author}</strong>
            <div style="display: flex; gap: 10px; font-size: 12px; color: #6b7280;">
              <span>@${item.channel}</span>
              <span>${new Date(item.date).toLocaleDateString()}</span>
            </div>
          </div>
          <p style="margin: 0; color: #374151; line-height: 1.5;">${item.text}</p>
        </div>
      `;

      timelineContainer.appendChild(timelineItem);
    });

    vizRef.current.appendChild(timelineContainer);
  };

  useEffect(() => {
    if (visLoaded && selectedChannelIds.length > 0) {
      renderVisualization();
    }
  }, [visLoaded, selectedChannelIds, searchQuery, visualizationType]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (networkRef.current) {
        networkRef.current.destroy();
      }
    };
  }, []);

  if (!visLoaded) {
    return (
      <Card withBorder p="md">
        <Group>
          <Loader size="sm" />
          <Text>Loading graph visualization...</Text>
        </Group>
      </Card>
    );
  }

  return (
    <Card withBorder p="md">
      <Stack>
        <Group>
          <Select
            label="Visualization Type"
            value={visualizationType}
            onChange={(value) => setVisualizationType(value || 'network')}
            data={[
              { value: 'network', label: 'Network Graph' },
              { value: 'timeline', label: 'Timeline View' }
            ]}
            style={{ minWidth: 200 }}
          />
          <Button 
            onClick={renderVisualization}
            loading={loading}
            disabled={selectedChannelIds.length === 0}
          >
            Refresh Visualization
          </Button>
        </Group>

        {loading && (
          <Group>
            <Loader size="sm" />
            <Text size="sm" c="dimmed">Loading visualization data...</Text>
          </Group>
        )}

        <div
          id="viz-container"
          ref={vizRef}
          style={{
            width: '100%',
            height: '500px',
            border: '1px solid #e9ecef',
            borderRadius: '8px',
            backgroundColor: '#fff'
          }}
        />

        {selectedChannelIds.length === 0 && (
          <Text c="dimmed" ta="center" py="xl">
            Select channels to view graph visualization
          </Text>
        )}
      </Stack>
    </Card>
  );
};

export default GraphVisualization;
import { useEffect, useRef, useState } from 'react';
import { IconInfoCircle } from '@tabler/icons-react';
import { Alert, Box, Card, Group, Loader, Slider, Stack, Text } from '@mantine/core';
import { authFetch } from '@/utils/authFetch';

interface GraphVisualizationProps {
  selectedChannelIds: string[];
  searchQuery?: string;
  user?: string | null;
  type?: string | null;
}

const GraphVisualization: React.FC<GraphVisualizationProps> = ({
  selectedChannelIds,
  searchQuery,
  user,
  type,
}) => {
  const vizRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<any>(null);
  const [loading, setLoading] = useState(false);
  const [visualizationType] = useState<string>('network');
  const [visLoaded, setVisLoaded] = useState(false);
  const [limit, setLimit] = useState(100);

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
    if (!visLoaded || !vizRef.current) {
      return;
    }

    // Clear previous visualization
    if (networkRef.current) {
      networkRef.current.destroy();
      networkRef.current = null;
    }

    // Prepare nodes with different colors for different types
    const getNodeColor = (nodeType: string) => {
      switch (nodeType) {
        case 'Channel':
          return {
            background: '#ff6b6b',
            border: '#ff5252',
            highlight: { background: '#ff8a80', border: '#ff1744' },
          };
        case 'User':
          return {
            background: '#4ecdc4',
            border: '#26c6da',
            highlight: { background: '#80e5ff', border: '#00acc1' },
          };
        case 'Message':
          return {
            background: '#ffd93d',
            border: '#ffcc02',
            highlight: { background: '#ffeb3b', border: '#ff8f00' },
          };
        default:
          return {
            background: '#95a5a6',
            border: '#7f8c8d',
            highlight: { background: '#bdc3c7', border: '#34495e' },
          };
      }
    };

    const nodes = data.nodes.map((node: any) => ({
      id: node.id,
      label: node.label,
      group: node.type,
      title: node.name || node.label,
      color: getNodeColor(node.type),
      size: Math.max((node.properties?.message_count || 1) * 2, 15),
      font: { size: 12, color: '#000000' },
    }));

    // Prepare edges with different colors for different relationship types
    const getEdgeColor = (relType: string) => {
      switch (relType) {
        case 'RECOMMENDS':
          return { color: '#e74c3c', highlight: '#c0392b', hover: '#c0392b' };
        case 'SENT':
          return { color: '#3498db', highlight: '#2980b9', hover: '#2980b9' };
        case 'IN_CHANNEL':
          return { color: '#f39c12', highlight: '#e67e22', hover: '#e67e22' };
        case 'POSTS_IN':
          return { color: '#2ecc71', highlight: '#27ae60', hover: '#27ae60' };
        case 'REPLIES_TO':
          return { color: '#9b59b6', highlight: '#8e44ad', hover: '#8e44ad' };
        default:
          return { color: '#848484', highlight: '#2196f3', hover: '#2196f3' };
      }
    };

    const edges = data.relationships.map((rel: any) => ({
      id: rel.id,
      from: rel.from,
      to: rel.to,
      label: rel.type,
      title: `${rel.type}${rel.properties?.message_count ? ` (${rel.properties.message_count} messages)` : ''}${rel.properties?.score ? ` (Score: ${rel.properties.score})` : ''}`,
      width: Math.min(Math.max(rel.properties?.message_count || rel.properties?.score || 1, 1), 10),
      arrows: 'to',
      color: getEdgeColor(rel.type),
      smooth: { type: 'continuous' },
    }));

    // Deduplicate nodes
    const seenNodeIds = new Set();
    const uniqueNodes = [];
    for (const node of nodes) {
      if (!seenNodeIds.has(node.id)) {
        seenNodeIds.add(node.id);
        uniqueNodes.push(node);
      }
    }

    // Deduplicate edges
    const seenEdgeIds = new Set();
    const uniqueEdges = [];
    for (const edge of edges) {
      if (!seenEdgeIds.has(edge.id)) {
        seenEdgeIds.add(edge.id);
        uniqueEdges.push(edge);
      }
    }

    const nodeDataset = new (window as any).vis.DataSet(uniqueNodes);
    const edgeDataset = new (window as any).vis.DataSet(uniqueEdges);

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
          face: 'Tahoma',
        },
      },
      edges: {
        width: 0.15,
        color: { inherit: 'from' },
        smooth: {
          type: 'continuous',
        },
      },
      physics: {
        enabled: true,
        barnesHut: {
          gravitationalConstant: -30000,
          centralGravity: 0.3,
          springLength: 95,
          springConstant: 0.04,
          damping: 0.09,
        },
        maxVelocity: 50,
        minVelocity: 0.1,
        solver: 'barnesHut',
        stabilization: { iterations: 80 },
        timestep: 0.35,
        adaptiveTimestep: true,
      },
      interaction: {
        tooltipDelay: 200,
        hideEdgesOnDrag: true,
        hideNodesOnDrag: false,
      },
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
        const node = nodes.find((n: { id: any }) => n.id === nodeId);
        console.log('Clicked node:', node);
      }
    });
  };

  const renderVisualization = async () => {
    if (!vizRef.current) {
      return;
    }

    setLoading(true);

    try {
      // Fetch data from our backend endpoint
      const response = await authFetch(
        `${import.meta.env.VITE_API_URL || 'http://localhost:8000/api'}/graph/visualization`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            channel_ids: selectedChannelIds,
            search_query: searchQuery,
            user: user || null,
            type: type || null,
            limit,
            visualization_type: visualizationType,
          }),
        }
      );

      const data = await response.json();

      if (visualizationType === 'network') {
        await renderNetworkVisualization(data);
      }
    } catch (error) {
      console.error('Error rendering visualization:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (visLoaded && selectedChannelIds.length > 0) {
      renderVisualization();
    }
  }, [visLoaded, selectedChannelIds, searchQuery, visualizationType, user, type]);

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
        <Stack>
          <Alert variant="light" color="blue" title="Graph Visualization" icon={<IconInfoCircle />}>
            In the "Messages"-Tab: Click on a username or the channel/group next to it, to update
            the graph.
          </Alert>
          <Text size="sm">Limit</Text>
          <Slider
            color="blue"
            mb="lg"
            labelAlwaysOn
            min={0}
            max={1000}
            value={limit}
            onChange={setLimit}
            onChangeEnd={() => {
              if (selectedChannelIds.length > 0) {
                renderVisualization();
              }
            }}
            marks={[
              { value: 100, label: '100' },
              { value: 500, label: '500' },
              { value: 1000, label: '1000' },
            ]}
          />
        </Stack>

        {loading && (
          <Group>
            <Loader size="sm" />
            <Text size="sm" c="dimmed">
              Loading visualization data...
            </Text>
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
            backgroundColor: '#fff',
          }}
        />

        {selectedChannelIds.length === 0 && (
          <Text c="dimmed" ta="center" py="xl">
            Select channels to view graph visualization
          </Text>
        )}

        {/* Legend */}
        <Group gap="lg" wrap="wrap">
          {[
            { label: 'Channel', color: '#ff6b6b' },
            { label: 'User', color: '#4ecdc4' },
            { label: 'Message', color: '#ffd93d' },
            { label: 'Other', color: '#95a5a6' },
          ].map(({ label, color }) => (
            <Group key={label} gap={6}>
              <Box style={{ width: 12, height: 12, borderRadius: '50%', backgroundColor: color, flexShrink: 0 }} />
              <Text size="xs" c="dimmed">{label}</Text>
            </Group>
          ))}
          <Text size="xs" c="dimmed" ml="auto">Edge label = relationship type</Text>
        </Group>
      </Stack>
    </Card>
  );
};

export default GraphVisualization;

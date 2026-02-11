import React, { useRef, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { useElementSize } from '@mantine/hooks';
import { Box, Paper, Text } from '@mantine/core';
import { GraphNode, GraphLink } from '../../services/agentService';

interface GraphRAGWidgetProps {
  data: {
    nodes: GraphNode[];
    links: GraphLink[];
  };
}

// Define the methods we need from the ForceGraph ref
interface ForceGraphRef {
  d3Force: (forceName: string) => any;
  zoomToFit: (duration?: number, padding?: number) => void;
}

export const GraphRAGWidget: React.FC<GraphRAGWidgetProps> = ({ data }) => {
  const { ref, width, height } = useElementSize();
  const fgRef = useRef<ForceGraphRef>(null);

  useEffect(() => {
    if (fgRef.current) {
        fgRef.current.d3Force('charge')?.strength(-100);
        fgRef.current.zoomToFit(400); 
    }
  }, [data]);

  const [showDebug, setShowDebug] = React.useState(false);
  const [selectedNode, setSelectedNode] = React.useState<any>(null);

  // Helper to format properties for display
  const renderProperties = (node: any) => {
      const props = node.properties || {};
      return Object.entries(props).map(([key, value]) => {
          if (key === 'embedding') return null; // Skip vectors
          if (typeof value === 'object') return null; // Skip complex objects for now
          return (
              <div key={key} style={{ marginBottom: 4 }}>
                  <Text size="xs" c="dimmed" style={{ textTransform: 'uppercase' }}>{key}</Text>
                  <Text size="sm" style={{ wordBreak: 'break-word' }}>{String(value)}</Text>
              </div>
          );
      });
  };

  return (
    <Paper shadow="sm" radius="md" withBorder h="100%" display="flex" style={{ flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
        
       {/* Header */}
       <Box p="sm" style={{ borderBottom: '1px solid #eee', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#fff', zIndex: 10 }}>
          <Text fw={600} size="sm">Context Graph</Text>
          <div style={{ display: 'flex', gap: 10 }}>
              <Text size="xs" c="dimmed">{data.nodes.length} Nodes • {data.links.length} Links</Text>
              <Text 
                size="xs" 
                c="blue" 
                style={{ cursor: 'pointer' }}
                onClick={() => setShowDebug(!showDebug)}
              >
                  {showDebug ? 'Hide Debug' : 'Debug'}
              </Text>
          </div>
       </Box>

       {/* Main Content Area - Relative positioning for absolute overlay */}
       <Box style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
           
           {/* Graph Canvas */}
           <Box ref={ref} style={{ width: '100%', height: '100%' }}>
               {!showDebug ? (
                <ForceGraph2D
                  ref={fgRef}
                  width={width}
                  height={height}
                  graphData={data}
                  // Intelligent Labeling
                  nodeLabel={(node: any) => {
                      const props = node.properties || {};
                      let label = props.name || props.text || props.original_text || props.title || props.username || node.name || node.label || node.id;
                      if (typeof label === 'string' && label.length > 50) label = label.substring(0, 50) + '...';
                      return `${node.label}: ${label}`;
                  }}
                  // Visuals - "Imposing" Style
                  nodeColor={(node: any) => {
                      if (node.id === selectedNode?.id) return '#FAB005'; // Highlight selected
                      if (node.label === 'Message') return '#228BE6'; // Blue
                      if (node.label === 'User') return '#FA5252';    // Red
                      if (node.label === 'Channel') return '#40C057'; // Green
                      if (node.label === 'Location') return '#F08C00'; // Orange
                      if (node.label === 'Emotion') return '#BE4BDB'; // Grape
                      return '#868e96'; // Grey default
                  }}
                  nodeVal={(node: any) => (node.id === selectedNode?.id ? 15 : (node.val || 8))}
                  nodeRelSize={6}
                  linkWidth={2}
                  linkColor={() => '#ced4da'}
                  linkDirectionalParticles={1} 
                  linkDirectionalParticleSpeed={0.005}
                  backgroundColor="#ffffff"
                  onNodeClick={(node: any) => {
                      setSelectedNode(node);
                      // Zoom to node?
                      fgRef.current?.d3Force('center'); // Release center constraints
                  }}
                  onEngineStop={() => fgRef.current?.zoomToFit(400)}
                  cooldownTicks={100}
                />
               ) : (
                <Box p="md" style={{ overflow: 'auto', height: '100%', background: '#f8f9fa' }}>
                   <pre style={{ fontSize: '0.75rem' }}>{JSON.stringify(data, null, 2)}</pre>
                </Box>
               )}
           </Box>

           {/* Detail Panel Overlay (Bottom Right) */}
           {selectedNode && !showDebug && (
               <Paper 
                  shadow="md" 
                  p="md" 
                  radius="md" 
                  withBorder
                  style={{ 
                      position: 'absolute', 
                      bottom: 16, 
                      right: 16, 
                      width: 300, 
                      maxHeight: '60%', 
                      overflowY: 'auto',
                      zIndex: 20,
                      background: 'rgba(255, 255, 255, 0.95)',
                      backdropFilter: 'blur(5px)'
                  }}
               >
                   <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                       <Text fw={700} color="blue">{selectedNode.label}</Text>
                       <Text 
                          size="xs" 
                          style={{ cursor: 'pointer' }} 
                          onClick={() => setSelectedNode(null)}
                       >
                           ✕ Close
                       </Text>
                   </div>
                   
                   <Text fw={600} size="sm" mb="xs">
                       {selectedNode.properties?.name || selectedNode.properties?.title || selectedNode.id}
                   </Text>
                   
                   <Box mt="sm">
                       {renderProperties(selectedNode)}
                   </Box>
               </Paper>
           )}

       </Box>
    </Paper>
  );
};

import React, { useRef, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { useElementSize } from '@mantine/hooks';
import { Box, Paper, Text, Badge, Group, ActionIcon, Tooltip } from '@mantine/core';
import { GraphNode, GraphLink } from '../../services/agentService';
import { IconZoomIn, IconZoomOut, IconFocusCentered } from '@tabler/icons-react';

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
  zoom: (k?: number) => number | undefined;
}

const EMOJI_MAP: Record<string, string> = {
    'Message': '💬',
    'User': '👤',
    'Channel': '📢',
    'Location': '📍',
    'Emotion': '🎭',
    'Classification': '🏷️',
    'Unknown': '❓'
};

const COLOR_MAP: Record<string, string> = {
    'Message': '#339AF0', // Blue
    'User': '#FF6B6B',    // Red
    'Channel': '#51CF66', // Green
    'Location': '#FF922B', // Orange
    'Emotion': '#CC5DE8', // Grape
    'Classification': '#845EF7', // Violet
    'Unknown': '#868e96'
};

const EDGE_COLOR_MAP: Record<string, string> = {
    'HAS_MESSAGE':        '#51CF66', // Green — channel → message
    'SENT':               '#FF6B6B', // Red — user → message
    'REPLY_TO':           '#339AF0', // Blue — message → message
    'MENTIONS_LOCATION':  '#FF922B', // Orange — message → location
    'HAS_EMOTION':        '#CC5DE8', // Grape — message → emotion
    'RECOMMENDS':         '#FAB005', // Yellow — channel → channel
    'PART_OF':            '#74C0FC', // Light blue
};

export const GraphRAGWidget: React.FC<GraphRAGWidgetProps> = ({ data }) => {
  const { ref, width, height } = useElementSize();
  const fgRef = useRef<ForceGraphRef>(null);

  // Initial Zoom
  useEffect(() => {
    if (fgRef.current && data.nodes.length > 0) {
        setTimeout(() => {
            fgRef.current?.d3Force('charge')?.strength(-200);
            fgRef.current?.d3Force('link')?.distance(70);
            fgRef.current?.zoomToFit(800, 50);
        }, 500);
    }
  }, [data]);

  const [selectedNode, setSelectedNode] = React.useState<any>(null);

  // Helper to format properties for display
  const renderProperties = (node: any) => {
      const props = node.properties || {};
      return Object.entries(props).map(([key, value]) => {
          if (key === 'embedding') return null;
          if (typeof value === 'object') return null;
          return (
              <div key={key} style={{ marginBottom: 4 }}>
                  <Text size="xs" c="dimmed" style={{ textTransform: 'uppercase', letterSpacing: '0.5px' }}>{key}</Text>
                  <Text size="sm" style={{ wordBreak: 'break-word', color: '#e0e0e0' }}>{String(value)}</Text>
              </div>
          );
      });
  };

  const handleZoomIn = () => {
      const currentZoom = fgRef.current?.zoom();
      if (currentZoom) fgRef.current?.zoom(currentZoom * 1.2);
  };
  
  const handleZoomOut = () => {
      const currentZoom = fgRef.current?.zoom();
      if (currentZoom) fgRef.current?.zoom(currentZoom / 1.2);
  };
  
  const handleRecenter = () => {
      fgRef.current?.zoomToFit(400, 50);
  };

  // Derive which node types and edge types are actually present in the data
  const presentNodeTypes = Array.from(new Set(data.nodes.map((n: any) => n.label))).filter(Boolean) as string[];
  const presentEdgeTypes = Array.from(new Set(data.links.map((l: any) => l.type))).filter(Boolean) as string[];

  return (
    <Paper 
        shadow="xl" 
        radius="lg" 
        withBorder 
        h="100%" 
        display="flex" 
        style={{ 
            flexDirection: 'column', 
            overflow: 'hidden', 
            position: 'relative',
            background: '#111827', // Almost black
            borderColor: '#374151'
        }}
    >
        
       {/* Header Overlay */}
       <Box 
            p="xs" 
            style={{ 
                position: 'absolute', 
                top: 0, 
                left: 0, 
                right: 0, 
                height: 50,
                zIndex: 10,
                background: 'linear-gradient(180deg, rgba(17,24,39,0.9) 0%, rgba(17,24,39,0) 100%)',
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                paddingLeft: 16,
                paddingRight: 16
            }}
       >
          <Group gap="xs">
            <Badge variant="filled" color="cyan" size="sm">GRAPH VIEW</Badge>
            <Text size="xs" c="dimmed">{data.nodes.length} items</Text>
          </Group>
          
          <Group gap={8}>
               <Tooltip label="Zoom In" position="bottom" withArrow>
                   <ActionIcon variant="subtle" color="gray" onClick={handleZoomIn}><IconZoomIn size={18}/></ActionIcon>
               </Tooltip>
               <Tooltip label="Zoom Out" position="bottom" withArrow>
                   <ActionIcon variant="subtle" color="gray" onClick={handleZoomOut}><IconZoomOut size={18}/></ActionIcon>
               </Tooltip>
               <Tooltip label="Recenter" position="bottom" withArrow>
                   <ActionIcon variant="subtle" color="gray" onClick={handleRecenter}><IconFocusCentered size={18}/></ActionIcon>
               </Tooltip>
          </Group>
       </Box>

       {/* Main Canvas */}
       <Box style={{ flex: 1, position: 'relative', overflow: 'hidden' }} ref={ref}>
           {width > 0 && height > 0 && (
            <ForceGraph2D
              ref={fgRef}
              width={width}
              height={height}
              graphData={data}
              backgroundColor="#111827" 
              // Custom Rendering
              nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
                  if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;
                  
                  const isSelected = node.id === selectedNode?.id;
                  const label = node.label || 'Unknown';
                  const color = COLOR_MAP[label] || '#868e96';
                  const emoji = EMOJI_MAP[label] || '❓';
                  
                  // Base size
                  const baseR = 6; 
                  
                  // Draw Glow (Radial Gradient)
                  const gradient = ctx.createRadialGradient(node.x, node.y, baseR * 0.5, node.x, node.y, baseR * 3);
                  gradient.addColorStop(0, color);
                  gradient.addColorStop(1, 'rgba(0,0,0,0)');
                  
                  ctx.beginPath();
                  ctx.fillStyle = gradient;
                  ctx.arc(node.x, node.y, baseR * 3, 0, 2 * Math.PI, false);
                  ctx.fill();
                  
                  // Draw Core Circle
                  ctx.beginPath();
                  ctx.arc(node.x, node.y, baseR, 0, 2 * Math.PI, false);
                  ctx.fillStyle = color;
                  ctx.fill();
                  
                  // Draw Selection Ring
                  if (isSelected) {
                      ctx.beginPath();
                      ctx.arc(node.x, node.y, baseR * 1.5, 0, 2 * Math.PI, false);
                      ctx.strokeStyle = '#fff';
                      ctx.lineWidth = 1 / globalScale;
                      ctx.stroke();
                  }

                  // Draw Emoji
                  const fontSize = 8;
                  ctx.font = `${fontSize}px Sans-Serif`;
                  ctx.textAlign = 'center';
                  ctx.textBaseline = 'middle';
                  ctx.fillStyle = 'white'; // Not needed for emoji really
                  ctx.fillText(emoji, node.x, node.y + 0.5); // Center vertically

                  // Draw Label (only if hovered or selected or zoomed in)
                  // Simplified: always draw text if globalScale > 1.5 OR selected
                  if (globalScale > 1.5 || isSelected) {
                      // Smart Label Selection
                      let name = node.properties?.name || node.properties?.title || node.properties?.username;
                      
                      // If no name/title, try text content for Messages
                      if (!name && (node.label === 'Message' || !node.label)) {
                          name = node.properties?.original_text || node.properties?.text || node.properties?.translated_text || node.id;
                      }
                      
                      // Fallback
                      if (!name) name = node.id;

                      const textLabel = name.length > 20 ? name.substring(0, 18) + '..' : name;
                      
                      const textY = node.y + baseR + 6;
                      const textFontSize = 4;
                      ctx.font = `${textFontSize}px Sans-Serif`;
                      ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
                      ctx.fillText(textLabel, node.x, textY);
                  }
              }}
              nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
                  ctx.fillStyle = color;
                  ctx.beginPath();
                  ctx.arc(node.x, node.y, 8, 0, 2 * Math.PI, false);
                  ctx.fill();
              }}
              
              linkWidth={1.5}
              linkColor={(link: any) => EDGE_COLOR_MAP[link.type] || '#4B5563'}
              linkDirectionalParticles={2}
              linkDirectionalParticleSpeed={0.005}
              linkDirectionalParticleWidth={2}
              linkDirectionalParticleColor={(link: any) => EDGE_COLOR_MAP[link.type] || '#4dabf7'}
              
              onNodeClick={(node: any) => {
                  setSelectedNode(node);
                  // Optional: Center on node
                  // fgRef.current?.centerAt(node.x, node.y, 1000);
                  // fgRef.current?.zoom(4, 1000);
              }}
              onBackgroundClick={() => setSelectedNode(null)}
              cooldownTicks={100}
            />
           )}
       </Box>

       {/* Legend — bottom left, only shows types present in this query result */}
       <Box
           style={{
               position: 'absolute',
               bottom: 16,
               left: 16,
               zIndex: 20,
               background: 'rgba(17, 24, 39, 0.85)',
               border: '1px solid #374151',
               borderRadius: 8,
               padding: '8px 12px',
               backdropFilter: 'blur(8px)',
               maxWidth: 200,
           }}
       >
           {presentNodeTypes.length > 0 && (
               <Box mb={presentEdgeTypes.length > 0 ? 6 : 0}>
                   {presentNodeTypes.map((type) => (
                       <Group key={type} gap={6} mb={2}>
                           <Box style={{ width: 10, height: 10, borderRadius: '50%', background: COLOR_MAP[type] || '#868e96', flexShrink: 0 }} />
                           <Text size="xs" c="dimmed">{EMOJI_MAP[type]} {type}</Text>
                       </Group>
                   ))}
               </Box>
           )}
           {presentEdgeTypes.length > 0 && (
               <Box style={{ borderTop: presentNodeTypes.length > 0 ? '1px solid #374151' : 'none', paddingTop: presentNodeTypes.length > 0 ? 6 : 0 }}>
                   {presentEdgeTypes.map((type) => (
                       <Group key={type} gap={6} mb={2}>
                           <Box style={{ width: 14, height: 2, background: EDGE_COLOR_MAP[type] || '#4B5563', flexShrink: 0 }} />
                           <Text size="xs" c="dimmed" style={{ fontSize: 10 }}>{type}</Text>
                       </Group>
                   ))}
               </Box>
           )}
       </Box>

       {/* Floating Detail Panel */}
       {selectedNode && (
           <Paper 
              shadow="xl" 
              p="md" 
              radius="md" 
              withBorder
              style={{ 
                  position: 'absolute', 
                  bottom: 16, 
                  right: 16, 
                  width: 320, 
                  maxHeight: '60%', 
                  overflowY: 'auto',
                  zIndex: 20,
                  background: 'rgba(31, 41, 55, 0.95)', // Dark
                  borderColor: '#374151',
                  backdropFilter: 'blur(10px)',
                  color: 'white'
              }}
           >
               <Group justify="space-between" mb="xs">
                   <Badge color={COLOR_MAP[selectedNode.label] || 'gray'} size="lg" variant="filled">
                       {EMOJI_MAP[selectedNode.label]} {selectedNode.label}
                   </Badge>
                   <ActionIcon variant="subtle" color="gray" size="sm" onClick={() => setSelectedNode(null)}>
                       ✕
                   </ActionIcon>
               </Group>
               
               <Text fw={700} size="md" mb="md" c="white">
                   {selectedNode.properties?.name || selectedNode.properties?.title || selectedNode.properties?.username || selectedNode.id}
               </Text>
               
               <Box>
                   {renderProperties(selectedNode)}
               </Box>
           </Paper>
       )}

    </Paper>
  );
};

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

  return (
    <Paper shadow="sm" p="md" radius="md" withBorder h="100%" display="flex" style={{ flexDirection: 'column' }}>
      <Text fw={500} mb="sm">Context Graph</Text>
      <Box ref={ref} style={{ flex: 1, minHeight: 400, overflow: 'hidden' }}>
        <ForceGraph2D
          ref={fgRef}
          width={width}
          height={height}
          graphData={data}
          nodeLabel={(node: any) => node.name || node.text || node.id}
          nodeAutoColorBy="label"
          linkDirectionalParticles={2}
          linkDirectionalParticleSpeed={0.005}
          nodeVal={(node: any) => node.val || 3}
          onNodeClick={(node: any, event: any) => {
             // Optional: Handle click
             console.log("Clicked node", node);
          }}
        />
      </Box>
    </Paper>
  );
};

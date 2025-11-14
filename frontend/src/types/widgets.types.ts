// src/types/widget.types.ts
export interface Widget {
  id: string;
  type: WidgetType;
  title: string;
  position: GridPosition;
  config: WidgetConfig;
  isLoading?: boolean;
  error?: string;
  lastUpdated?: Date;
}

export interface GridPosition {
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
  maxW?: number;
  maxH?: number;
}

export type WidgetType = 
  | 'top-posts'
  | 'top-influencers'
  | 'emotion-analysis'
  | 'location-heatmap'
  | 'case-overview'
  | 'metrics-summary'
  | 'message-timeline'
  | 'geographic-map'
  | 'neo4j-network'
  | 'ai-chatbot';

export interface WidgetConfig {
  refreshInterval?: number;
  dataSource?: string;
  filters?: Record<string, any>;
  visualization?: VisualizationConfig;
  [key: string]: any;
}

export interface VisualizationConfig {
  chartType?: 'bar' | 'line' | 'pie' | 'area' | 'scatter';
  colorScheme?: string[];
  showLegend?: boolean;
  showGrid?: boolean;
}

export interface WidgetDefinition {
  type: WidgetType;
  name: string;
  description: string;
  icon: React.ComponentType;
  component: React.ComponentType<WidgetComponentProps>;
  defaultConfig: WidgetConfig;
  defaultSize: { w: number; h: number; minW?: number; minH?: number };
  categories: string[];
  configSchema?: WidgetConfigSchema;
}

export interface WidgetComponentProps {
  widget: Widget;
  onUpdate: (config: Partial<WidgetConfig>) => void;
  onRemove: () => void;
  isEditing: boolean;
}

export interface WidgetConfigSchema {
  fields: ConfigField[];
}

export interface ConfigField {
  name: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'channel-multiselect';
  description?: string;
  defaultValue?: any;
  placeholder?: string;
  options?: { value: string; label: string }[];
  validation?: {
    required?: boolean;
    min?: number;
    max?: number;
  };
}

export interface DashboardLayout {
  id: string;
  name: string;
  widgets: Widget[];
  isDefault?: boolean;
  createdAt: Date;
  updatedAt: Date;
}

export interface WidgetData<T = any> {
  data: T;
  loading: boolean;
  error: Error | null;
  refetch: () => void;
}
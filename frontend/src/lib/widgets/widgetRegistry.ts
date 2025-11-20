// src/lib/widgets/widgetRegistry.ts
import { WidgetDefinition, WidgetType } from '@/types/widgets.types';
import { 
  IconChartBar, 
  IconUsers, 
  IconMoodSmile, 
  IconMapPin,
  IconFiles,
  IconChartLine,
  IconTimeline,
  IconMap,
  IconNetwork,
  IconRobot
} from '@tabler/icons-react';

import { TopPostsWidget } from '@/components/widgets/TopPostsWidget';
import { TopInfluencersWidget } from '@/components/widgets/TopInfluencersWidget';
import { EmotionAnalysisWidget } from '@/components/widgets/EmotionAnalysisWidget';
import { LocationHeatmapWidget } from '@/components/widgets/LocationHeatmapWidget';
import { LocationMapWidget } from '@/components/widgets/LocationMapWidget';


class WidgetRegistry {
  private widgets: Map<WidgetType, WidgetDefinition> = new Map();

  constructor() {
    this.registerDefaultWidgets();
  }

  private registerDefaultWidgets() {
    // Dashboard Widgets
    this.register({
      type: 'top-posts',
      name: 'Top Posts',
      description: 'Display the top 5 most relevant posts across channels',
      icon: IconChartBar,
      component: TopPostsWidget,
      defaultConfig: {
        refreshInterval: 60000,
        filters: {
          channelIds: [],
          keywords: '',
          limit: 5,
          sortBy: 'relevance'
        }
      },
      defaultSize: { w: 6, h: 4, minW: 4, minH: 3 },
      categories: ['dashboard', 'analytics'],
      configSchema: {
        fields: [
          {
            name: 'filters.channelIds',
            label: 'Channels',
            type: 'channel-multiselect',
            description: 'Select which channels to monitor',
            validation: { required: true }
          },
          {
            name: 'filters.keywords',
            label: 'Keywords (Optional)',
            type: 'text',
            description: 'Filter messages by keywords',
            placeholder: 'e.g., climate, corona, news...'
          },
          {
            name: 'filters.limit',
            label: 'Number of Posts',
            type: 'number',
            defaultValue: 5,
            description: 'How many top posts to display',
            validation: { min: 1, max: 20, required: true }
          },
          {
            name: 'filters.sortBy',
            label: 'Sort By',
            type: 'select',
            description: 'How to rank the posts',
            options: [
              { value: 'relevance', label: 'Relevance' },
              { value: 'recent', label: 'Most Recent' },
              { value: 'engagement', label: 'Engagement' }
            ]
          }
        ]
      }
      
    });
    this.register({
  type: 'top-influencers',
  name: 'Top Influencers',
  description: 'Display the top 5 most active and influential posters',
  icon: IconUsers,
  component: TopInfluencersWidget,
  defaultConfig: {
    refreshInterval: 60000,
    filters: {
      channelIds: [],
      limit: 5,
      sortBy: 'engagement'
    }
  },
  defaultSize: { w: 6, h: 4, minW: 4, minH: 3 },
  categories: ['dashboard', 'analytics'],
  configSchema: {
    fields: [
      {
        name: 'filters.channelIds',
        label: 'Channels',
        type: 'channel-multiselect',
        validation: { required: true }
      },
      {
        name: 'filters.limit',
        label: 'Number of Influencers',
        type: 'number',
        defaultValue: 5,
        validation: { min: 1, max: 20, required: true }
      }
    ]
  }
});

this.register({
  type: 'emotion-analysis',
  name: 'Emotion Analysis',
  description: 'Analyze and visualize emotional sentiment distribution',
  icon: IconMoodSmile,
  component: EmotionAnalysisWidget,
  defaultConfig: {
    refreshInterval: 60000,
    filters: {
      channelIds: [],
      limit: 5
    }
  },
  defaultSize: { w: 6, h: 3, minW: 4, minH: 3 },
  categories: ['dashboard', 'analytics'],
  configSchema: {
    fields: [
      {
        name: 'filters.channelIds',
        label: 'Channels',
        type: 'channel-multiselect',
        validation: { required: true }
      },
      {
        name: 'filters.limit',
        label: 'Number of Emotions',
        type: 'number',
        defaultValue: 5,
        validation: { min: 3, max: 10, required: true }
      }
    ]
  }
});

this.register({
  type: 'location-heatmap',
  name: 'Location Heatmap',
  description: 'Display the top mentioned locations',
  icon: IconMapPin,
  component: LocationHeatmapWidget,
  defaultConfig: {
    refreshInterval: 60000,
    filters: {
      channelIds: [],
      limit: 5
    }
  },
  defaultSize: { w: 6, h: 4, minW: 4, minH: 3 },
  categories: ['dashboard', 'analytics'],
  configSchema: {
    fields: [
      {
        name: 'filters.channelIds',
        label: 'Channels',
        type: 'channel-multiselect',
        validation: { required: true }
      },
      {
        name: 'filters.limit',
        label: 'Number of Locations',
        type: 'number',
        defaultValue: 5,
        validation: { min: 1, max: 20, required: true }
      }
    ]
  }
});
    this.register({
      type: 'location-map',
      name: 'Location Map',
      description: 'Interactive map showing message locations',
      icon: IconMap,
      component: LocationMapWidget,
      defaultConfig: {
        refreshInterval: 60000,
        filters: {
          channelIds: []
        }
      },
      defaultSize: { w: 6, h: 4, minW: 4, minH: 3 },
      categories: ['dashboard', 'analytics'],
      configSchema: {
        fields: [
          {
            name: 'filters.channelIds',
            label: 'Channels',
            type: 'channel-multiselect',
            validation: { required: true }
          }
        ]
      }
    });
  }

  register(definition: WidgetDefinition) {
    this.widgets.set(definition.type, definition);
  }

  unregister(type: WidgetType) {
    this.widgets.delete(type);
  }

  get(type: WidgetType): WidgetDefinition | undefined {
    return this.widgets.get(type);
  }

  getAll(): WidgetDefinition[] {
    return Array.from(this.widgets.values());
  }

  getByCategory(category: string): WidgetDefinition[] {
    return this.getAll().filter(widget => 
      widget.categories.includes(category)
    );
  }

  exists(type: WidgetType): boolean {
    return this.widgets.has(type);
  }
}

export const widgetRegistry = new WidgetRegistry();

export const registerWidget = (definition: WidgetDefinition) => 
  widgetRegistry.register(definition);

export const getWidget = (type: WidgetType) => 
  widgetRegistry.get(type);

export const getWidgetsByCategory = (category: string) => 
  widgetRegistry.getByCategory(category);
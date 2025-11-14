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
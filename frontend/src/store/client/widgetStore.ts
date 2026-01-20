// src/store/widgetStore.ts
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { Widget, DashboardLayout, WidgetType, GridPosition, WidgetConfig } from '@/types/widgets.types';
import { v4 as uuidv4 } from 'uuid';

interface WidgetState {
  // Dashboard layouts
  layouts: DashboardLayout[];
  activeLayoutId: string | null;
  
  // Widget management
  widgets: Record<string, Widget[]>; // Keyed by layout ID
  
  // Edit mode
  isEditMode: boolean;
  selectedWidgetId: string | null;
  
  // Actions - Layout Management
  createLayout: (name: string) => DashboardLayout;
  updateLayout: (layoutId: string, updates: Partial<DashboardLayout>) => void;
  deleteLayout: (layoutId: string) => void;
  setActiveLayout: (layoutId: string) => void;
  duplicateLayout: (layoutId: string, newName: string) => DashboardLayout;
  
  // Actions - Widget Management
  addWidget: (layoutId: string, type: WidgetType, position?: Partial<GridPosition>) => Promise<Widget>;
  updateWidget: (layoutId: string, widgetId: string, updates: Partial<Widget>) => void;
  removeWidget: (layoutId: string, widgetId: string) => void;
  moveWidget: (layoutId: string, widgetId: string, position: GridPosition) => void;
  duplicateWidget: (layoutId: string, widgetId: string) => Widget;
  updateWidgetConfig: (layoutId: string, widgetId: string, config: Partial<WidgetConfig>) => void;
  
  // Actions - Bulk Operations
  updateWidgetPositions: (layoutId: string, positions: { id: string; position: GridPosition }[]) => void;
  clearLayout: (layoutId: string) => void;
  importLayout: (layout: DashboardLayout) => void;
  exportLayout: (layoutId: string) => DashboardLayout | null;
  
  // Actions - Edit Mode
  setEditMode: (enabled: boolean) => void;
  selectWidget: (widgetId: string | null) => void;
  
  // Getters
  getActiveLayout: () => DashboardLayout | null;
  getLayoutWidgets: (layoutId: string) => Widget[];
  getWidget: (layoutId: string, widgetId: string) => Widget | undefined;
}

// Default layout configuration
const createDefaultLayout = (): DashboardLayout => ({
  id: uuidv4(),
  name: 'Default Dashboard',
  widgets: [
    {
       id: uuidv4(),
       type: 'agent-query',
       title: 'Agent Query',
       position: { x: 0, y: 0, w: 12, h: 6, minW: 6, minH: 4 },
       config: {}
    }
  ],
  isDefault: true,
  createdAt: new Date(),
  updatedAt: new Date(),
});

export const useWidgetStore = create<WidgetState>()(
  persist(
    (set, get) => ({
      // Initial state
      layouts: [createDefaultLayout()],
      activeLayoutId: null,
      widgets: {},
      isEditMode: false,
      selectedWidgetId: null,

      // Layout Management
      createLayout: (name) => {
        const newLayout: DashboardLayout = {
          id: uuidv4(),
          name,
          widgets: [],
          isDefault: false,
          createdAt: new Date(),
          updatedAt: new Date(),
        };
        
        set((state) => ({
          layouts: [...state.layouts, newLayout],
          widgets: { ...state.widgets, [newLayout.id]: [] },
        }));
        
        return newLayout;
      },

      updateLayout: (layoutId, updates) => {
        set((state) => ({
          layouts: state.layouts.map((layout) =>
            layout.id === layoutId
              ? { ...layout, ...updates, updatedAt: new Date() }
              : layout
          ),
        }));
      },

      deleteLayout: (layoutId) => {
        set((state) => {
          const newWidgets = { ...state.widgets };
          delete newWidgets[layoutId];
          
          return {
            layouts: state.layouts.filter((l) => l.id !== layoutId),
            widgets: newWidgets,
            activeLayoutId: state.activeLayoutId === layoutId ? null : state.activeLayoutId,
          };
        });
      },

      setActiveLayout: (layoutId) => {
        set({ activeLayoutId: layoutId });
      },

      duplicateLayout: (layoutId, newName) => {
        const originalLayout = get().layouts.find((l) => l.id === layoutId);
        if (!originalLayout) throw new Error('Layout not found');
        
        const newLayout: DashboardLayout = {
          ...originalLayout,
          id: uuidv4(),
          name: newName,
          isDefault: false,
          createdAt: new Date(),
          updatedAt: new Date(),
        };
        
        const originalWidgets = get().widgets[layoutId] || [];
        const duplicatedWidgets = originalWidgets.map((widget) => ({
          ...widget,
          id: uuidv4(),
        }));
        
        set((state) => ({
          layouts: [...state.layouts, newLayout],
          widgets: { ...state.widgets, [newLayout.id]: duplicatedWidgets },
        }));
        
        return newLayout;
      },

      // Widget Management
      addWidget: async (layoutId, type, position) => {
        const widgetRegistry = await import('@/lib/widgets/widgetRegistry').then(m => m.widgetRegistry);
        const definition = widgetRegistry.get(type);
        
        if (!definition) {
          throw new Error(`Widget type ${type} not found in registry`);
        }
        
        const newWidget: Widget = {
          id: uuidv4(),
          type,
          title: definition.name,
          position: {
            x: position?.x ?? 0,
            y: position?.y ?? 0,
            w: position?.w ?? definition.defaultSize.w,
            h: position?.h ?? definition.defaultSize.h,
            minW: definition.defaultSize.minW,
            minH: definition.defaultSize.minH,
          },
          config: { ...definition.defaultConfig },
        };
        
        set((state) => ({
          widgets: {
            ...state.widgets,
            [layoutId]: [...(state.widgets[layoutId] || []), newWidget],
          },
        }));
        
        return newWidget;
      },

      updateWidget: (layoutId, widgetId, updates) => {
        set((state) => ({
          widgets: {
            ...state.widgets,
            [layoutId]: (state.widgets[layoutId] || []).map((widget) =>
              widget.id === widgetId
                ? { ...widget, ...updates }
                : widget
            ),
          },
        }));
      },

      removeWidget: (layoutId, widgetId) => {
        set((state) => ({
          widgets: {
            ...state.widgets,
            [layoutId]: (state.widgets[layoutId] || []).filter(
              (widget) => widget.id !== widgetId
            ),
          },
          selectedWidgetId: state.selectedWidgetId === widgetId ? null : state.selectedWidgetId,
        }));
      },

      moveWidget: (layoutId, widgetId, position) => {
        get().updateWidget(layoutId, widgetId, { position });
      },

      duplicateWidget: (layoutId, widgetId) => {
        const widget = get().getWidget(layoutId, widgetId);
        if (!widget) throw new Error('Widget not found');
        
        const duplicated: Widget = {
          ...widget,
          id: uuidv4(),
          position: {
            ...widget.position,
            x: (widget.position.x + 1) % 12, // Offset position slightly
            y: widget.position.y + widget.position.h,
          },
        };
        
        set((state) => ({
          widgets: {
            ...state.widgets,
            [layoutId]: [...(state.widgets[layoutId] || []), duplicated],
          },
        }));
        
        return duplicated;
      },

      updateWidgetConfig: (layoutId, widgetId, config) => {
        const widget = get().getWidget(layoutId, widgetId);
        if (!widget) return;
        
        get().updateWidget(layoutId, widgetId, {
          config: { ...widget.config, ...config },
        });
      },

      // Bulk Operations
      updateWidgetPositions: (layoutId, positions) => {
        set((state) => ({
          widgets: {
            ...state.widgets,
            [layoutId]: (state.widgets[layoutId] || []).map((widget) => {
              const newPosition = positions.find((p) => p.id === widget.id);
              return newPosition
                ? { ...widget, position: newPosition.position }
                : widget;
            }),
          },
        }));
      },

      clearLayout: (layoutId) => {
        set((state) => ({
          widgets: {
            ...state.widgets,
            [layoutId]: [],
          },
        }));
      },

      importLayout: (layout) => {
        set((state) => ({
          layouts: [...state.layouts, layout],
          widgets: {
            ...state.widgets,
            [layout.id]: layout.widgets || [],
          },
        }));
      },

      exportLayout: (layoutId) => {
        const layout = get().layouts.find((l) => l.id === layoutId);
        if (!layout) return null;
        
        return {
          ...layout,
          widgets: get().widgets[layoutId] || [],
        };
      },

      // Edit Mode
      setEditMode: (enabled) => {
        set({ isEditMode: enabled, selectedWidgetId: enabled ? null : null });
      },

      selectWidget: (widgetId) => {
        set({ selectedWidgetId: widgetId });
      },

      // Getters
      getActiveLayout: () => {
        const state = get();
        return state.layouts.find((l) => l.id === state.activeLayoutId) || null;
      },

      getLayoutWidgets: (layoutId) => {
        return get().widgets[layoutId] || [];
      },

      getWidget: (layoutId, widgetId) => {
        return (get().widgets[layoutId] || []).find((w) => w.id === widgetId);
      },
    }),
    {
      name: 'aether-widget-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        layouts: state.layouts,
        widgets: state.widgets,
        activeLayoutId: state.activeLayoutId,
      }),
      onRehydrateStorage: () => (state) => {
        // Initialize with default layout if none exists
        if (state && state.layouts.length === 0) {
          const defaultLayout = createDefaultLayout();
          state.layouts = [defaultLayout];
          state.activeLayoutId = defaultLayout.id;
          state.widgets[defaultLayout.id] = [];
        }
      },
    }
  )
);
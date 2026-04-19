# Step 6 — Dashboard

The **Dashboard** is your main monitoring surface. It shows live data from your scraped channels through a set of customizable, resizable widgets that you arrange yourself.

Access it via the grid icon in the sidebar, or navigate to `/`.

---

## 6.1 Overview

![Dashboard base view](assets/aether_dashboard_base_view_highlighted_menu_button_in_widget.png)

The dashboard displays all your active widgets side by side. Each widget has a small toolbar in the top-right corner with **refresh**, **resize**, and a **menu** (⋯) button.

The **View Mode** toggle in the top-right switches between read-only view and edit mode.

---

## 6.2 Adding Widgets

Click **+ Add Widget** (top right, visible in Edit Mode) to open the widget picker.

![Add widget dialog](assets/aether_dashboard_add_widget_view.png)

The following widgets are available:

| Widget | Description |
|--------|-------------|
| **Agent Query** | Embed the AI agent chat directly in your dashboard |
| **Top Posts** | The 5 most relevant posts across selected channels |
| **Top Influencers** | The 5 most active and influential senders |
| **Emotion Analysis** | Donut chart of emotional sentiment distribution |
| **Location Heatmap** | Top mentioned locations ranked by count |
| **Location Map** | Interactive map of geo-tagged message locations |

Click **+** on any widget to add it to the dashboard.

---

## 6.3 Configuring a Widget

Every widget needs to know which channels to monitor. Open the widget menu via the **⋯** button and select **Configure**.

![Widget context menu](assets/aether_dashboard_configure_widget_button.png)

This opens the configuration panel:

![Configure widget — set channels](assets/aether_dashboard_configure_set_channels.png)

| Setting | Description |
|---------|-------------|
| **Channels** | Select one or more scraped channels to use as the data source |
| **Refresh Interval (ms)** | How often the widget polls for new data — set to `0` to disable auto-refresh |

Click **Save Configuration** to apply. The widget will immediately reload with data from the selected channels.

---

## 6.4 Edit Mode — Drag, Resize & Arrange

Toggle **Edit Mode** to freely rearrange the dashboard layout.

![Edit mode — drag and resize](assets/aether_dashboard_edit_mode_activated_widgets_drag_and_pull_resizable.png)

In edit mode you can:

- **Drag** any widget to a new position
- **Resize** by pulling the bottom-right corner handle
- **Rename** or **Duplicate** a widget via the ⋯ menu
- **Remove** a widget via the ⋯ menu → Remove

Turn off Edit Mode when done — the layout is saved automatically.

---

## 6.5 Rearranged Layout

After adding and configuring multiple widgets, your dashboard might look like this:

![Rearranged dashboard with multiple widgets](assets/aether_dashboard_rearranged_view_added_widget.png)

Widgets update independently on their own refresh cycle. The **Location Map** shows clustered geo-pins, **Top Posts** shows ranked messages with relevance scores, and **Emotion Analysis** shows the dominant emotion distribution as a donut chart.

---

**Next:** [Step 7 — Reports](07-reports.md)

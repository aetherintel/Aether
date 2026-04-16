# Step 5 — Agent Chat

The **Agent Chat** is an AI-powered interface for querying and visualizing your case data using natural language or slash commands.

Access it via the **Agent** icon (🤖) in the sidebar, or via the **Visuals** tab inside a case.

---

## 5.1 Input & Commands

Type in the input field to get suggestions. The suggestions change depending on what you type:

- Start with `/` → shows available **slash commands**
- Type anything else → shows **example natural language queries**

![Agent commands](assets/aether_agent_default_commands.png)

### Slash Commands

| Command | Description |
|---------|-------------|
| `/showmap [filter]` | Render an interactive map of extracted locations |
| `/visualize <query>` | Force a graph visualization of relationships |
| `/summarize [query]` | Generate a natural language summary |
| `/help` | List all available commands |

You can use commands with or without the `/` prefix — both work.

---

## 5.2 Example Queries

The agent understands natural language. Below are queries that are known to work well, organized by what they return.

### Maps

These queries return an **interactive location map** with clickable markers and message previews.

| Query | What it shows |
|-------|---------------|
| `Show map of mentioned locations` | All geo-tagged locations across your data |
| `/showmap` | Same as above via slash command |
| `Show map of negative emotions` | Locations from messages tagged with anger, fear, hatred, despair, or distrust |
| `Show map of anger and fear` | Locations specifically from messages expressing anger or fear |
| `Show map where Ukraine is mentioned` | Locations from messages containing the word "Ukraine" |
| `Show map of propaganda channels` | Locations from channels with propaganda classifications |
| `/showmap negative emotions` | Same as the natural language version |

> **Tip:** Click any map marker to see the location name, mention count, and up to 3 recent messages that reference it.

---

### Graphs

These queries return a **node-link graph** of relationships between entities.

| Query | What it shows |
|-------|---------------|
| `Visualize channels and their recommended channels` | Channel recommendation network |
| `Visualize channels connected by shared users` | Channels that share active users |
| `Visualize channels sharing the most locations` | Channels linked by common geo-references |
| `Visualize the reply chain of the most replied-to message` | Conversation thread tree |
| `Visualize the user reply network` | Who replies to whom |
| `Visualize channels with negative emotions` | Channels and their emotion types (anger, fear, etc.) |
| `Visualize user interaction network about politics` | Reply network filtered to political messages |

> **Tip:** Use the graph to identify coordinated channels, key amplifiers, or unusual reply patterns.

---

### Tables & Charts

These queries return **tables or bar/pie charts**.

| Query | What it shows |
|-------|---------------|
| `Which channels are most active?` | Channel message counts, ranked |
| `Who are the most active senders?` | Top users by message count |
| `What are the dominant emotions across all messages?` | Emotion distribution as a chart |
| `Show emotion distribution per channel` | Emotion breakdown by channel |
| `What are the most common message categories?` | Classification/topic distribution |
| `Which channels have the most violence or threat content?` | Channels with Gewalt/Bedrohung classifications |
| `What are the top 15 most mentioned locations?` | Location ranking by mention count |
| `Show message volume over the last 30 days` | Daily message trend over time |
| `How many messages have been scraped in total?` | Single total count |

---

### Tables with Sample Messages

These queries return a **table including actual message text** alongside the counts.

| Query | What it shows |
|-------|---------------|
| `Show channels with negative emotions and 5 sample messages` | Channel, emotion type, count, and 5 example messages per row |

---

## 5.3 Location Map

The agent renders geo-extracted locations on an interactive map.

**Overview map** — clustered markers across Germany:

![Agent map overview](assets/aether_agent_default_map.png)

**Zoomed cluster** — clicking a cluster zooms in and shows individual pins with mention counts:

![Agent map with OSINT overlay](assets/aether_agent_default_map_osint.png)

**Location popup** — click any marker to see mention count and recent messages referencing that location:

![Agent map with message preview](assets/aether_agent_map_with_message_preview.png)

**Satellite view** — toggle the map layer for satellite imagery with OSINT overlays:

![Agent satellite map](assets/aether_agent_satellitemap_with_osint.png)

> **Umfeld-Scan** — the button on a selected marker triggers an area scan, surfacing nearby OSINT data points.

---

## 5.4 Graph Visuals

The **Visualize** command returns a graph of nodes and relationships from the Neo4j database. The model receives the schema and tries to match your query to known relationship patterns (channels → messages → emotions → locations, etc.).

![Agent Graph Visual](assets/aether_agent_graph_visual.png)

---

## 5.5 Feedback & Query Debugging

Every agent response that ran a database query shows a small toolbar at the bottom of the message:

| Button | Action |
|--------|--------|
| 👍 | Mark the result as good — saved and used to improve future queries |
| 👎 | Mark the result as bad — logged for review |
| `</>` | Toggle the generated Cypher query for inspection |

Use the Cypher view to verify exactly what was queried against the database.

---

## 5.6 Re-Index

Use the **Re-Index** button (top right of Agent Chat) to rebuild the vector search index after large scraping jobs. This improves the agent's ability to match your questions to relevant examples.

---

**Next:** [Step 6 — Reports](06-reports.md)

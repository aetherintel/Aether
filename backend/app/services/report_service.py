from pathlib import Path
from datetime import datetime, timedelta, timezone
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import base64
import os
import seaborn as sns
import networkx as nx

# Import services
from services.neo4j_backend_client import (
    get_messages_with_media,
    get_channel_list,
    get_total_message_count_for_channels,
    get_top_locations,
    get_message_volume_over_time,
    get_channel_recommendation_graph,
    get_user_interaction_graph,
    get_user_interaction_graph,
    get_active_channels_in_period,
    get_aggregated_emotions
)


REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "/shared/reports"))
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Setup Jinja2 environment
# Assumes this file is in backend/app/services/
env = Environment(loader=FileSystemLoader(Path(__file__).parent.parent / "templates"))

# Set style for charts
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("deep")

def generate_bar_chart_base64(data: dict, title: str, xlabel: str = "", ylabel: str = "") -> str:
    """Generate clean bar chart as base64 string"""
    if not data:
        return ""
        
    fig, ax = plt.subplots(figsize=(10, 6))
    
    keys = list(data.keys())
    values = list(data.values())
    
    # Create bars with a single professional color or a clean palette
    bars = ax.bar(keys, values, color='#4c72b0', alpha=0.8)
    
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    
    # Rotate labels if needed
    plt.xticks(rotation=45, ha='right')
    
    # Add grid for readability
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=10)
    
    plt.tight_layout()
    
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150)
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()
    
    return f"data:image/png;base64,{img_base64}"

def generate_line_chart_base64(data: list[dict], title: str) -> str:
    """Generate clean line chart for time series"""
    if not data:
        return ""
        
    dates = [datetime.fromisoformat(d['date']) for d in data]
    counts = [d['count'] for d in data]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(dates, counts, marker='o', linestyle='-', linewidth=2, color='#4c72b0')
    ax.fill_between(dates, counts, alpha=0.2, color='#4c72b0')
    
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    ax.set_ylabel("Message Count", fontsize=12)
    
    # Add grid
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150)
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()
    
    return f"data:image/png;base64,{img_base64}"

def generate_network_graph_base64(graph_data: dict, title: str) -> str:
    """Generate network graph visualization"""
    if not graph_data or not graph_data["nodes"]:
        return ""
        
    G = nx.Graph()
    for node in graph_data["nodes"]:
        G.add_node(node["id"], label=node["label"])
    for edge in graph_data["edges"]:
        G.add_edge(edge["source"], edge["target"], weight=edge.get("weight", 1))
        
    plt.figure(figsize=(10, 8))
    
    # Calculate layout
    pos = nx.spring_layout(G, k=0.5, iterations=50)
    
    # Draw nodes
    degrees = dict(G.degree())
    node_sizes = [v * 100 + 300 for v in degrees.values()]
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color='#4c72b0', alpha=0.8)
    
    # Draw edges
    nx.draw_networkx_edges(G, pos, width=1.0, alpha=0.5, edge_color='#999')
    
    # Draw labels
    nx.draw_networkx_labels(G, pos, font_size=8, font_family='sans-serif')
    
    plt.title(title, fontsize=14, fontweight='bold')
    plt.axis('off')
    
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()
    
    return f"data:image/png;base64,{img_base64}"

def generate_pie_chart_base64(data: dict, title: str) -> str:
    """Generate clean pie chart as base64 string"""
    if not data:
        return ""
        
    labels = list(data.keys())
    sizes = list(data.values())
    
    # Custom colors mapping for specific emotions if possible, else default palette
    emotions_colors = {
        'positive': '#2ecc71',
        'negative': '#e74c3c',
        'neutral': '#95a5a6',
        'angry': '#e67e22',
        'sad': '#3498db',
        'Freude / Zufriedenheit': '#2ecc71',
        'Wut / Aggression': '#e74c3c',
        'Trauer / Mitgefühl': '#3498db',
        'Angst / Bedrohungsempfinden': '#9b59b6',
    }
    
    colors = [emotions_colors.get(l, None) for l in labels]
    
    fig, ax = plt.subplots(figsize=(8, 8))
    
    wedges, texts, autotexts = ax.pie(
        sizes, 
        labels=labels, 
        autopct='%1.1f%%',
        startangle=90,
        pctdistance=0.85,
        colors=colors,
        textprops=dict(color="black")
    )
    
    # Draw circle for Donut Chart style
    centre_circle = plt.Circle((0,0),0.70,fc='white')
    fig.gca().add_artist(centre_circle)
    
    ax.axis('equal')  
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    
    plt.tight_layout()
    
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150)
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()
    
    return f"data:image/png;base64,{img_base64}"

def calculate_graph_kpis(graph_data: dict) -> dict:
    """Calculate basic graph metrics"""
    if not graph_data or not graph_data["nodes"]:
        return {}
        
    G = nx.Graph()
    for node in graph_data["nodes"]:
        G.add_node(node["id"])
    for edge in graph_data["edges"]:
        G.add_edge(edge["source"], edge["target"])
        
    if len(G.nodes) == 0:
        return {}
        
    # Degree Centrality (Top Influencer)
    degree_centrality = nx.degree_centrality(G)
    top_influencer = max(degree_centrality.items(), key=lambda x: x[1])[0] if degree_centrality else "N/A"
    
    # Density
    density = nx.density(G)
    
    # Connected Components
    components = nx.number_connected_components(G)
    
    return {
        "top_influencer": top_influencer,
        "density": f"{density:.2f}",
        "components": components,
        "node_count": len(G.nodes),
        "edge_count": len(G.edges)
    }

async def get_case_details(case_id: int):
    # Placeholder for case details
    return {"name": f"Case #{case_id}", "id": case_id}

async def get_case_statistics(owner_id: str, start_date: datetime, end_date: datetime):
    """
    Fetch comprehensive stats for the report.
    """
    # 1. Active Channels (using period filter to fix discrepancy)
    active_channels = await get_active_channels_in_period(owner_id, start_date, end_date)
    active_channels_count = len(active_channels)
    
    # 2. Total Messages
    total_messages = sum(c['message_count'] for c in active_channels)
    
    # 3. Message Volume Over Time
    volume_data = await get_message_volume_over_time(owner_id, start_date, end_date)
    
    # 4. Top Locations
    top_locations = await get_top_locations(owner_id, limit=10, before=end_date)
    
    # 5. Channel Distribution (Top 10 from active)
    sorted_channels = sorted(active_channels, key=lambda x: x['message_count'], reverse=True)[:10]
    channel_dist = {c['title'] or c['username']: c['message_count'] for c in sorted_channels}
    
    # 6. Graph Data
    rec_graph = await get_channel_recommendation_graph(owner_id)
    graph_kpis = calculate_graph_kpis(rec_graph)

    # 7. Emotion Data
    emotions = await get_aggregated_emotions(owner_id, start_date=start_date, end_date=end_date)
    emotion_dist = {e['emotion']: e['count'] for e in emotions} if emotions else {}
    
    return {
        "total_messages": total_messages,
        "active_channels": active_channels_count,
        "channels": channel_dist,
        "volume_over_time": volume_data,
        "top_locations": top_locations,
        "graph_data": rec_graph,
        "graph_kpis": graph_kpis,
        "emotions": emotion_dist
    }

async def get_recent_messages(owner_id: str, limit: int = 50):
    return await get_messages_with_media(owner_id=owner_id, limit=limit)

async def create_report_pdf(case_id: int, owner_id: str, period: str, sections: list[str] = None):
    """
    Core logic to generate PDF report.
    """
    if sections is None:
        sections = ["stats", "charts", "messages"]
        
    # Calculate date range (Use UTC to match Neo4j DateTime)
    end_date = datetime.now(timezone.utc)
    if period == "daily":
        start_date = end_date - timedelta(days=1)
    elif period == "weekly":
        start_date = end_date - timedelta(weeks=1)
    elif period == "monthly":
        start_date = end_date - timedelta(days=30)
    else:  # all_time or default
        # Set start date to a very old date to include everything
        start_date = end_date - timedelta(days=3650) # 10 years
    
    # Fetch data
    case_data = await get_case_details(case_id)
    
    stats = None
    if "stats" in sections or "charts" in sections:
        stats = await get_case_statistics(owner_id, start_date, end_date)
    
    messages = []
    if "messages" in sections:
        messages = await get_recent_messages(owner_id, limit=50)
    
    # Generate charts
    chart_data = {}
    if "charts" in sections and stats:
        if stats["channels"]:
            chart_data["channel_distribution"] = generate_bar_chart_base64(
                stats["channels"], 
                "Top Active Channels",
                ylabel="Message Count"
            )
            
        if stats["volume_over_time"]:
            chart_data["message_volume"] = generate_line_chart_base64(
                stats["volume_over_time"],
                "Message Volume Over Time"
            )
            
        if stats["top_locations"]:
            loc_data = {l["name"]: l["count"] for l in stats["top_locations"]}
            chart_data["top_locations"] = generate_bar_chart_base64(
                loc_data,
                "Top Mentioned Locations",
                ylabel="Mentions"
            )
            
            chart_data["network_graph"] = generate_network_graph_base64(
                stats["graph_data"],
                "Channel Recommendation Network"
            )
            
        if stats.get("emotions"):
            chart_data["emotions"] = generate_pie_chart_base64(
                stats["emotions"],
                "Emotion Analysis"
            )
    
    # Prepare message objects for template
    formatted_messages = []
    for msg in messages:
        formatted_messages.append({
            "date": msg["date"],
            "channel_name": msg["channel"]["title"] or msg["channel"]["username"],
            "text": msg["original_text"] or msg["translated_text"] or "[Media]",
            "author": msg["author"]["name"]
        })

    # Render HTML template
    template = env.get_template("report_template.html")
    html_content = template.render(
        case=case_data,
        period=period,
        start_date=start_date,
        end_date=end_date,
        stats=stats,
        messages=formatted_messages,
        charts=chart_data,
        sections=sections,
        generated_at=datetime.now()
    )
    
    # Create case-specific directory
    case_dir = REPORTS_DIR / f"case_{case_id}"
    case_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate PDF
    filename = f"report_{case_id}_{period}_{end_date.strftime('%Y%m%d')}.pdf"
    filepath = case_dir / filename
    
    HTML(string=html_content).write_pdf(
        filepath,
        stylesheets=[CSS(string="""
            @page { size: A4; margin: 2cm; }
            body { font-family: 'Helvetica', 'Arial', sans-serif; color: #333; line-height: 1.5; font-size: 12px; }
            h1 { color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; }
            h2 { color: #34495e; margin-top: 30px; border-bottom: 1px solid #eee; padding-bottom: 5px; }
            .header { text-align: center; margin-bottom: 40px; }
            .meta { color: #7f8c8d; font-size: 0.9em; margin-bottom: 30px; }
            .stat-box { background: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 4px solid #3498db; }
            .chart { page-break-inside: avoid; margin-bottom: 30px; text-align: center; }
            table { width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 0.9em; }
            th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
            th { background-color: #f2f2f2; color: #2c3e50; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            .kpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px; }
            .kpi-card { background: #fff; border: 1px solid #ddd; padding: 10px; text-align: center; border-radius: 4px; }
            .kpi-value { font-size: 1.5em; font-weight: bold; color: #2c3e50; }
            .kpi-label { font-size: 0.8em; color: #7f8c8d; }
        """)]
    )
    
    return filename, filepath

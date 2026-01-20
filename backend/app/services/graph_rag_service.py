from typing import List, Dict, Any, Optional
import os
from langchain_community.graphs import Neo4jGraph
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_neo4j import Neo4jVector

class GraphRAGService:
    def __init__(self):
        self.url = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        self.username = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD")
        
        # Initialize LangChain Neo4j integration
        self.graph = Neo4jGraph(
            url=self.url,
            username=self.username,
            password=self.password
        )
        
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small"
        )
        
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0
        )

    async def _hydrate_message_context(self):
        """
        Updates ALL Message nodes with a 'context_text' property that combines
        text + emotion + specific metadata for better semantic search.
        """
        query = """
        MATCH (m:Message)
        WHERE m.text IS NOT NULL
        OPTIONAL MATCH (m)-[:HAS_EMOTION]->(e:Emotion)
        WITH m, collect(e.name) as emotions
        
        MATCH (ch:Channel)-[:HAS_MESSAGE]->(m)
        
        WITH m, emotions, ch
        
        SET m.context_text = 
            "Content: " + coalesce(m.text, "") + "\\n" +
            "Channel: " + coalesce(ch.title, ch.username, "") + "\\n" +
            "Emotions: " + coalesce(reduce(s = "", x IN emotions | s + x + ", "), "None")
        """
        # Note: We use a separate session for this maintenance task
        # Ideally this runs in batches, but for now we run it globally (poc).
        self.graph.query(query)

    async def initialize_vector_index(self):
        """
        Creates or loads the vector index on Message nodes.
        """
        # First ensure we have data to index (hydrate context)
        await self._hydrate_message_context()
        
        self.vector_index = Neo4jVector.from_existing_graph(
            embedding=self.embeddings,
            url=self.url,
            username=self.username,
            password=self.password,
            index_name="message_vector_index",
            node_label="Message",
            text_node_properties=["context_text"], 
            embedding_node_property="embedding",
            metadata_node_properties=["mid", "owner_id", "date"] # Metadata for filtering and retrieval
        )

    async def run_dashboard_query(self, query: str, user_id: str) -> Dict[str, Any]:
        """
        Main entry point for the Dashboard Agent.
        1. Embed query
        2. Vector Search (filtered by owner_id=user_id)
        3. Graph Traversal (retrieve metadata for found nodes)
        4. Generate Summary
        5. Return Payload
        """
        # 1. Vector Search with Security Filter
        # Note: Neo4jVector allows filtering. The exact syntax depends on the underlying store implementation
        try:
            results = self.vector_index.similarity_search(
                query, 
                k=10, 
                filter={"owner_id": user_id}
            )
        except Exception as e:
            # Fallback or empty if index not ready
            print(f"Vector search failed: {e}")
            results = []

        if not results:
            return {
                "summary": "I couldn't find any relevant messages matching your query.",
                "visualization": {"type": "graph", "data": {"nodes": [], "links": []}}
            }

        # 2. Extract Message IDs
        message_ids = [r.metadata.get("mid") for r in results if r.metadata.get("mid")]
        
        # 3. Retrieve Subgraph (Graph Expansion)
        # We want to show the Message, its Channel, any Locations, and Emotions
        graph_query = """
        MATCH (m:Message)
        WHERE m.mid IN $messageIds
        
        OPTIONAL MATCH (ch:Channel)-[:HAS_MESSAGE]->(m)
        OPTIONAL MATCH (m)-[:HAS_EMOTION]->(e:Emotion)
        OPTIONAL MATCH (m)-[:MENTIONS_LOCATION]->(l:Location)
        
        RETURN m, ch, collect(e) as emotions, collect(l) as locations
        """
        
        graph_data = self.graph.query(graph_query, params={"messageIds": message_ids})
        
        # 4. Format Graph for Frontend (react-force-graph-2d structure)
        nodes = []
        links = []
        seen_nodes = set()
        
        for record in graph_data:
            m = record['m']
            ch = record['ch']
            emotions = record['emotions']
            locations = record['locations']
            
            # Message Node
            if m['mid'] not in seen_nodes:
                nodes.append({"id": m['mid'], "label": "Message", "text": m.get('text', '')[:50]+"...", "val": 3})
                seen_nodes.add(m['mid'])
            
            # Channel Node
            if ch and ch['channel_id'] not in seen_nodes:
                nodes.append({"id": ch['channel_id'], "label": "Channel", "name": ch.get('title', ch.get('username')), "val": 5})
                seen_nodes.add(ch['channel_id'])
                links.append({"source": ch['channel_id'], "target": m['mid']})
                
            # Emotion Nodes
            for e in emotions:
                eid = f"emotion_{e['name']}"
                if eid not in seen_nodes:
                    nodes.append({"id": eid, "label": "Emotion", "name": e['name'], "val": 2})
                    seen_nodes.add(eid)
                links.append({"source": m['mid'], "target": eid})
                
            # Location Nodes
            for l in locations:
                lid = f"loc_{l['location']}"
                if lid not in seen_nodes:
                    nodes.append({"id": lid, "label": "Location", "name": l['location'], "val": 4})
                    seen_nodes.add(lid)
                links.append({"source": m['mid'], "target": lid})

        # 5. Generate Summary with LLM
        # We construct a context string from the results
        context_str = "\\n".join([f"Msg: {r.page_content}" for r in results])
        
        prompt = f"""
        You are an intelligent assistant analyzing Telegram messages.
        User Query: "{query}"
        
        Found Messages:
        {context_str}
        
        Please provide a concise summary or answer based ONLY on the found messages.
        If the messages don't answer the query, say so.
        """
        
        llm_response = self.llm.invoke(prompt)
        
        return {
            "summary": llm_response.content,
            "visualization": {
                "type": "graph",
                "data": {"nodes": nodes, "links": links}
            }
        }



import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from services.text2cypher_service import Text2CypherService

logger = logging.getLogger(__name__)

class AgentResponse(BaseModel):
    message: str
    widget_type: Optional[str] = None
    widget_data: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = {}

class AgentService:
    def __init__(self):
        self.text2cypher = Text2CypherService()
        self.system_prompts = {
            "default": "You are Aether, a helpful AI assistant for analyzing Telegram message data. You can visualize graphs, summarize trends, and answer questions about messages, channels, users, and locations.",
            "data_analyst": "You are a data analyst specializing in message analytics. Focus on trends, statistics, distributions, and patterns. Provide insights with specific numbers and percentages. Use bullet points for clarity.",
            "storyteller": "You are a storyteller who weaves narrative from data. Transform query results into engaging stories that highlight key events, actors, and developments. Make the data come alive with context.",
            "programmer": "You are a Python expert and Neo4j specialist. Explain technical concepts clearly with code examples when relevant. Focus on data structures and algorithms.",
            "investigator": "You are a digital investigator. Focus on finding connections, anomalies, and suspicious patterns. Look for unusual activity, outliers, and potential risks. Provide actionable insights."
        }

    async def process_message(self, message: str, history: List[str] = [], system_prompt_key: str = "default", owner_id: Optional[str] = None) -> AgentResponse:
        """
        Main entry point for the agent. Parses commands or delegates to LLM/Text2Cypher.
        """
        logger.info(f"Agent received: {message} with prompt {system_prompt_key}, owner_id={owner_id}")

        # 1. Command Parsing
        if message.startswith("/"):
            return await self._handle_command(message, history, owner_id=owner_id)

        # 2. Intent Detection: map-related questions bypass the LLM
        msg_lower = message.lower()
        if any(phrase in msg_lower for phrase in ["show map", "map of", "show locations", "location map", "where are", "locations on map", "mentioned locations", "location visualization"]):
            return await self._handle_showmap(message, owner_id=owner_id)

        try:
            result = await self.text2cypher.run_text2cypher(message, history, system_prompt_key=system_prompt_key, owner_id=owner_id)
            
            return AgentResponse(
                message=result.get("summary", ""),
                widget_type=result.get("visualization", {}).get("type"),
                widget_data=result.get("visualization", {}).get("data"),
                metadata={"cypher": result.get("cypher"), "question": result.get("question")}
            )
        except Exception as e:
            logger.error(f"Agent processing failed: {e}")
            return AgentResponse(message=f"I encountered an error: {str(e)}")

    async def _handle_command(self, message: str, history: List[str], owner_id: Optional[str] = None) -> AgentResponse:
        parts = message.split(" ", 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command == "/help":
            return AgentResponse(
                message="**Available Commands:**\n"
                        "- `/visualize <query>`: Force a graph visualization.\n"
                        "- `/showmap <query>`: Generate a map visualization of locations.\n"
                        "- `/summarize <text/query>`: Summarize the results."
            )
        
        elif command == "/visualize":
            return await self.process_message(args, history, owner_id=owner_id)

        elif command in ["/showmap", "/show_map"]:
            # Bypass LLM entirely — execute a hardcoded location query and return map widget directly
            return await self._handle_showmap(args, owner_id=owner_id)

        elif command == "/summarize":
             args = f"Summarize the following: {args}" if args else "Summarize the last context."
             return await self.process_message(args, history, "storyteller", owner_id=owner_id) 
        
        elif command == "/sys":
            subcmd_parts = args.split(" ", 1)
            subcmd = subcmd_parts[0].lower() if subcmd_parts else ""
            
            if subcmd == "list":
                prompts_list = "\n".join([f"- `{k}`: {v[:50]}..." for k, v in self.system_prompts.items()])
                return AgentResponse(message=f"**System Prompts:**\n{prompts_list}")
            
            return AgentResponse(message="Usage: `/sys list` or `/sys set <key>`")

        return AgentResponse(message=f"Unknown command: `{command}`. Type `/help` for available commands.")

    async def _handle_showmap(self, filter_hint: str = "", owner_id: Optional[str] = None) -> AgentResponse:
        """
        Shows a location map. If a filter hint is given (e.g. "negative emotions"), uses the LLM
        to build a filtered query that still returns flat lat/lng columns for the map widget.
        Falls back to a hardcoded all-locations query when no filter is specified.
        """
        # Determine whether the user supplied a meaningful filter beyond just trigger phrases
        stripped = filter_hint.lower()
        for phrase in ["show map", "map of", "/showmap", "/show_map", "show locations",
                        "location map", "where are", "locations on map", "mentioned locations",
                        "location visualization", "showmap of the"]:
            stripped = stripped.replace(phrase, "")
        has_filter = len(stripped.strip()) > 3

        if has_filter:
            # Use the LLM but force the result to return flat location columns for the map widget.
            # We allow an extra aggregation column for ordering (e.g. count(e)) but the five
            # mandatory map columns must always be present so the map widget can render pins.
            map_question = (
                f"{filter_hint}. "
                "IMPORTANT: Build a Cypher query that answers this question AND returns results "
                "suitable for a map widget. "
                "The query MUST always return these five columns (use these exact aliases): "
                "l.latitude AS lat, l.longitude AS lng, l.canonical_name AS canonical_name, "
                "l.country AS country, l.mention_count AS mention_count. "
                "If ordering or filtering by a count (e.g. number of emotions, messages), add that "
                "as an ADDITIONAL return column with an alias and use it in ORDER BY. "
                "Example for 'locations with most emotions': "
                "MATCH (m:Message)-[:MENTIONS_LOCATION]->(l:Location), (m)-[:HAS_EMOTION]->(e:Emotion) "
                "RETURN l.latitude AS lat, l.longitude AS lng, l.canonical_name AS canonical_name, "
                "l.country AS country, l.mention_count AS mention_count, count(e) AS emotion_count "
                "ORDER BY emotion_count DESC LIMIT 10. "
                "Do NOT return full node variables — only flat properties plus any extra aggregation columns."
            )
            try:
                result = await self.text2cypher.run_text2cypher(
                    map_question, [], system_prompt_key="default", owner_id=owner_id
                )
                data = result.get("visualization", {}).get("data") or []
                cypher = result.get("cypher", "")
                # Validate that the result actually has lat/lng columns
                if data and isinstance(data, list) and ("lat" in data[0] or "latitude" in data[0]):
                    return AgentResponse(
                        message=f"**Map of {len(data)} locations**",
                        widget_type="location_map",
                        widget_data=data,
                        metadata={"cypher": cypher}
                    )
                # Query returned 0 results or wrong columns — fall through to all-locations fallback
                logger.warning("LLM map query returned no matching data, falling back to all-locations query")
            except Exception as e:
                logger.error(f"LLM map query failed: {e}, falling back to all-locations query")

        fallback_note = (
            "ℹ️ *Für deine Anfrage gibt es leider keine passenden Daten. "
            "Hier ist stattdessen eine allgemeine Karte aller Orte.*\n\n"
            if has_filter else ""
        )

        # Hardcoded fallback: all locations for this owner
        if owner_id:
            cypher = (
                "MATCH (m:Message)-[:MENTIONS_LOCATION]->(l:Location) "
                f"WHERE m.owner_id = '{owner_id}' AND l.latitude IS NOT NULL AND l.longitude IS NOT NULL "
                "RETURN l.latitude AS lat, l.longitude AS lng, "
                "l.canonical_name AS canonical_name, l.country AS country, "
                "l.mention_count AS mention_count "
                "ORDER BY l.mention_count DESC LIMIT 500"
            )
        else:
            cypher = (
                "MATCH (m:Message)-[:MENTIONS_LOCATION]->(l:Location) "
                "WHERE l.latitude IS NOT NULL AND l.longitude IS NOT NULL "
                "RETURN l.latitude AS lat, l.longitude AS lng, "
                "l.canonical_name AS canonical_name, l.country AS country, "
                "l.mention_count AS mention_count "
                "ORDER BY l.mention_count DESC LIMIT 500"
            )
        try:
            data = await self.text2cypher._execute_query(cypher)
            if not data:
                return AgentResponse(
                    message="No location data found. Run a scrape with geolocation extraction enabled.",
                    widget_type="table",
                    widget_data=[],
                    metadata={"cypher": cypher}
                )
            return AgentResponse(
                message=f"{fallback_note}**Karte mit {len(data)} Orten**",
                widget_type="location_map",
                widget_data=data,
                metadata={"cypher": cypher}
            )
        except Exception as e:
            logger.error(f"showmap failed: {e}")
            return AgentResponse(message=f"Failed to load location data: {e}")

    async def save_feedback(self, question: str, cypher: str, rating: int) -> bool:
        """
        Saves user feedback to a JSON file.
        Rating: 1 (derived from thumb up) or -1 (thumb down).
        Only saves positive feedback (+1) as few-shot examples for now.
        """
        import json
        import os
        
        FEEDBACK_FILE = "/app/feedback.json"
        
        # We only want to learn from GOOD examples (Rating > 0)
        # Bad examples could be used for "negative constraints" later, but for few-shot we want "Do This".
        if rating < 1:
            logger.info(f"Ignoring negative feedback for learning: {question}")
            return True # Successfully "processed" (ignored)

        entry = {
            "question": question,
            "cypher": cypher,
            "rating": rating,
            "timestamp": "TODO_add_timestamp"
        }

        try:
            existing = []
            if os.path.exists(FEEDBACK_FILE):
                try:
                    with open(FEEDBACK_FILE, 'r') as f:
                        content = f.read()
                        if content:
                            existing = json.loads(content)
                except Exception as read_err:
                     logger.warning(f"Could not read existing feedback: {read_err}")
            
            # Check for duplicates (overwrite if exists?)
            # Let's just append or update based on question
            updated = False
            for i, ex in enumerate(existing):
                if ex.get("question") == question:
                    existing[i] = entry # Update
                    updated = True
                    break
            
            if not updated:
                existing.append(entry)
            
            with open(FEEDBACK_FILE, 'w') as f:
                json.dump(existing, f, indent=2)
                
            logger.info(f"Saved feedback for: {question}")
            return True
        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")
            return False

    async def get_system_prompts(self) -> Dict[str, str]:
        return self.system_prompts

    async def get_suggested_commands(self) -> List[Dict[str, str]]:
        """
        Returns a list of suggested commands/queries for the frontend autocomplete.
        """
        return [
            {"category": "Commands", "label": "Visualize Graph", "query": "/visualize "},
            {"category": "Commands", "label": "Show Map", "query": "/showmap "},
            {"category": "Commands", "label": "Summarize Data", "query": "/summarize "},
            {"category": "Commands", "label": "Help", "query": "/help"}
        ]


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
            # Inject instruction to extract location data and use a persona good at data extraction
            enhanced_args = f"{args}. Ensure you return location names as canonical_name, latitude as lat, and longitude as lng in the results."
            return await self.process_message(enhanced_args, history, system_prompt_key="data_analyst", owner_id=owner_id)

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


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
            "default": "You are a helpful Aether assistant. You can visualize data, summarize cases, and answer questions.",
            "data_analyst": "You are a data analyst. Focus on trends, statistics, and graph structures.",
            "storyteller": "You are a storyteller. Summarize events as a narrative.",
            "programmer": "You are a python expert. Provide code snippets and technical explanations."
        }

    async def process_message(self, message: str, history: List[str] = [], system_prompt_key: str = "default") -> AgentResponse:
        """
        Main entry point for the agent. Parses commands or delegates to LLM/Text2Cypher.
        """
        logger.info(f"Agent received: {message} with prompt {system_prompt_key}")

        # 1. Command Parsing
        if message.startswith("/"):
            return await self._handle_command(message, history)

        # 2. Default Behavior (Text2Cypher for now, but wrapped)
        # In the future, we can decide based on system prompt whether to use Text2Cypher or just chat.
        # For now, let's assume everything is a data query unless specified otherwise.
        
        # We need to inject the system prompt logic into Text2Cypher or handle it here.
        # Since Text2Cypher is specific to graph generation, we might want a General Conversation Agent too.
        # For this step, we will wrap the Text2Cypher result.
        
        try:
            # TODO: Pass system prompt to Text2Cypher if possible, or use a general LLM for non-graph questions.
            # detailed_prompt = self.system_prompts.get(system_prompt_key, self.system_prompts["default"])
            
            result = await self.text2cypher.run_text2cypher(message, history, system_prompt_key=system_prompt_key)
            
            return AgentResponse(
                message=result.get("summary", ""),
                widget_type=result.get("visualization", {}).get("type"),
                widget_data=result.get("visualization", {}).get("data"),
                metadata={"cypher": result.get("cypher"), "question": result.get("question")}
            )
        except Exception as e:
            logger.error(f"Agent processing failed: {e}")
            return AgentResponse(message=f"I encountered an error: {str(e)}")

    async def _handle_command(self, message: str, history: List[str]) -> AgentResponse:
        parts = message.split(" ", 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command == "/help":
            return AgentResponse(
                message="**Available Commands:**\n"
                        "- `/visualize <query>`: Force a graph visualization.\n"
                        "- `/summarize <text/query>`: Summarize the results.\n"
                        "- `/sys list`: List available system prompts.\n"
                        "- `/sys set <key>`: Set the active system prompt (client-side mostly)."
            )
        
        elif command == "/visualize":
            # Force graph visualization
            return await self.process_message(args, history) 

        elif command == "/summarize":
             # For now, just pass it through as a normal message but with a summarization hint
             # Ideally we would call a summarization chain
             args = f"Summarize the following: {args}" if args else "Summarize the last context."
             return await self.process_message(args, history, "storyteller") 
        
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
        Ideally this could be dynamic based on user role or case context.
        """
        return [
            # Exploration
            {"category": "Exploration", "label": "Latest Messages", "query": "Show me the latest 20 messages"},
            {"category": "Exploration", "label": "Active Channels", "query": "Show me the channels with the most messages"},
            {"category": "Exploration", "label": "Media Content", "query": "Show me messages with photos or videos"},

            # Analysis
            {"category": "Analysis", "label": "Negative Sentiment", "query": "Show me messages with negative emotions"},
            {"category": "Analysis", "label": "Violent Content", "query": "Show me messages classified as violence"},
            {"category": "Analysis", "label": "Keyword Search", "query": "Find messages containing 'war' or 'conflict'"},

            # Visualization
            {"category": "Visualization", "label": "Channel Network", "query": "Visualize the connection between Channels and Messages"},
            {"category": "Visualization", "label": "Location Map", "query": "Visualize messages and their locations"},
            {"category": "Visualization", "label": "User Interactions", "query": "Visualize relationships between Users and Messages"},

            # Network
            {"category": "Network", "label": "Message Threads", "query": "Show me message threads (replies)"},
            {"category": "Network", "label": "Shared Locations", "query": "Show me locations mentioned by multiple channels"}
        ]

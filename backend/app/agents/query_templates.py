
import re
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class QueryTemplates:
    """
    Regex-based templates to bypass LLM for common queries.
    Returns a JSON plan structure compatible with Text2CypherService.
    """
    
    @staticmethod
    def match(question: str) -> Optional[Dict[str, Any]]:
        q = question.strip().lower()
        
        # 1. Latest Messages
        # "latest messages", "newest messages", "show me the last 50 messages"
        if re.search(r'\b(latest|newest|last)\b.*\b(messages?|posts?)\b', q) or q == "messages":
            limit = 50
            match_limit = re.search(r'\b(\d+)\b', q)
            if match_limit:
                limit = int(match_limit.group(1))
                
            return {
                "nodes": [{"id": "m", "label": "Message"}],
                "relationships": [],
                "optional_relationships": [],
                "filters": [],
                "return_fields": ["m"],
                "order_by": "m.date DESC",
                "limit": limit
            }

        # 2. Location Search
        # "messages from berlin", "messages in kyiv", "show messages mentioning paris"
        loc_match = re.search(r'\b(from|in|mentioning|about)\b\s+([A-Z][a-zA-Z\s]+)', question) # Case sensitive for City?
        # Actually simplified: look for "from X"
        if loc_match:
            city = loc_match.group(2).strip()
            # If city looks like a valid name (not "the", "my", etc.)
            if len(city) > 2 and city.lower() not in ["the", "my", "date", "user", "channel"]:
                return {
                    "nodes": [{"id": "m", "label": "Message"}],
                    "relationships": [], 
                    "optional_relationships": [],
                    "filters": [
                        {"variable": "m.location_names", "operator": "IN", "value": city}
                    ],
                    "return_fields": ["m"],
                    "order_by": "m.date DESC",
                    "limit": 50
                }

        # 3. Emotion Search
        # "angry messages", "show fear", "messages with joy"
        emotions = ["anger", "angry", "fear", "joy", "happy", "sadness", "sad", "surprise", "disgust", "love"]
        for emo in emotions:
            if emo in q:
                # Map adj to noun if needed, or just use partial match/mapped value
                emo_val = emo
                if emo == "angry": emo_val = "anger"
                if emo == "happy": emo_val = "joy"
                if emo == "sad": emo_val = "sadness"
                
                return {
                    "nodes": [{"id": "m", "label": "Message"}],
                    "relationships": [],
                    "optional_relationships": [],
                    "filters": [
                        {"variable": "m.emotions", "operator": "IN", "value": emo_val}
                    ],
                    "return_fields": ["m"],
                    "order_by": "m.date DESC",
                    "limit": 50
                }
        
        # 4. Channel Search
        # "messages from channel WarNews"
        ch_match = re.search(r'channel\s+([a-zA-Z0-9_]+)', question, re.IGNORECASE)
        if ch_match:
            ch_name = ch_match.group(1)
            return {
                "nodes": [{"id": "m", "label": "Message"}, {"id": "ch", "label": "Channel"}],
                "relationships": [
                    {"source": "ch", "target": "m", "type": "HAS_MESSAGE"}
                ],
                "optional_relationships": [],
                "filters": [
                    {"variable": "ch.username", "operator": "CONTAINS", "value": ch_name}
                ],
                "return_fields": ["m"],
                "order_by": "m.date DESC",
                "limit": 50
            }

        # 5. User Search
        # "messages from user John"
        user_match = re.search(r'user\s+([a-zA-Z0-9_]+)', question, re.IGNORECASE)
        if user_match:
            u_name = user_match.group(1)
            return {
                "nodes": [{"id": "m", "label": "Message"}, {"id": "u", "label": "User"}],
                "relationships": [
                    {"source": "u", "target": "m", "type": "SENT"}
                ],
                "optional_relationships": [],
                "filters": [
                    {"variable": "u.username", "operator": "CONTAINS", "value": u_name}
                ],
                "return_fields": ["m"],
                "order_by": "m.date DESC",
                "limit": 50
            }

        # 6. Keyword Search (Fallback if "about X" is used)
        # "messages about tanks"
        # EXCLUDE: location-related questions and questions asking for analysis (should use LLM for these)
        about_match = re.search(r'\babout\s+(.+)', q)
        if about_match:
            term = about_match.group(1)
            # Exclude location-related questions - should go to LLM
            if any(kw in q for kw in ["location", "place", "city", "country"]):
                return None
            # Exclude questions asking "what is/are" - these need analysis
            if "what is" in q or "what are" in q:
                return None
            # Exclude strict keywords
            if term not in ["the", "latest", "newest"]:
                 # Search both original and translated text for best coverage
                 # (original may be in a foreign language, translated is German)
                 return {
                    "nodes": [{"id": "m", "label": "Message"}],
                    "relationships": [],
                    "optional_relationships": [],
                    "filters": [
                        {"variable": "m.original_text", "operator": "CONTAINS", "value": term},
                        {"variable": "m.translated_text", "operator": "OR_CONTAINS", "value": term}
                    ],
                    "return_fields": ["m"],
                    "order_by": "m.date DESC",
                    "limit": 50
                }
                
        # 7. Visualization Request
        # "visualize messages and locations"
        if "visualize" in q or "graph" in q:
            # Simple heuristic: visualize MENTIONS_LOCATION if locations mentioned
            if "location" in q or "place" in q:
                 return {
                    "nodes": [{"id": "m", "label": "Message"}, {"id": "l", "label": "Location"}],
                    "relationships": [
                        {"source": "m", "target": "l", "type": "MENTIONS_LOCATION"}
                    ],
                    "optional_relationships": [],
                    "filters": [],
                    "return_fields": ["m", "l"],
                    "order_by": "m.date DESC",
                    "limit": 100
                 }

        # 9. Threads / Replies (Priority over Visuals)
        # "message threads", "replies", "conversations"
        if re.search(r'\b(threads?|replies|conversations?)\b', q):
             filters = []
             # Sub-filter: Visuals in threads
             if re.search(r'\b(visuals?|images?|photos?|videos?|media)\b', q):
                 filters.append({"variable": "m.media_type", "operator": "IN", "value": ["photo", "video", "document"]})

             return {
                "nodes": [{"id": "m", "label": "Message"}, {"id": "p", "label": "Message"}],
                "relationships": [
                    {"source": "m", "target": "p", "type": "REPLY_TO"}
                ],
                "optional_relationships": [],
                "filters": filters,
                "return_fields": ["m", "r", "p"],
                "order_by": "m.date DESC",
                "limit": 50
            }

        # 8. Visual Media Request
        # "messages with visuals", "show photos", "videos"
        if re.search(r'\b(visuals?|images?|photos?|videos?|media)\b', q):
             return {
                "nodes": [{"id": "m", "label": "Message"}],
                "relationships": [],
                "optional_relationships": [],
                "filters": [
                    {"variable": "m.media_type", "operator": "IN", "value": ["photo", "video", "document"]}
                ],
                "return_fields": ["m"],
                "order_by": "m.date DESC",
                "limit": 50
            }

        return None

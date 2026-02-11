# backend/app/agents/static_examples.py

STATIC_EXAMPLES = [
    {
        "keywords": ["thread", "reply", "conversation", "discussion"],
        "question": "Show me the thread starting with message 123",
        "cypher": "MATCH (root:Message {mid: '123'})-[:REPLY_TO*0..]->(reply:Message) RETURN root, reply ORDER BY reply.date ASC"
    },
    {
        "keywords": ["visual", "image", "photo", "video", "media"],
        "question": "Show messages with visuals from Berlin",
        "cypher": "MATCH (m:Message) WHERE m.media_type IN ['photo', 'video'] AND 'Berlin' IN m.location_names RETURN m ORDER BY m.date DESC LIMIT 20"
    },
    {
        "keywords": ["sentiment", "emotion", "feeling", "anger", "joy", "fear"],
        "question": "Summarize the sentiment of messages about politics",
        "cypher": "MATCH (m:Message) WHERE m.text CONTAINS 'politics' RETURN m.emotions, count(*) ORDER BY count(*) DESC"
    },
    {
        "keywords": ["popular", "top", "viral", "most"],
        "question": "Show me the most popular messages",
        "cypher": "MATCH (m:Message) RETURN m ORDER BY m.views DESC, m.forwards DESC LIMIT 10"
    },
    {
        "keywords": ["user", "sender", "from"],
        "question": "Messages from user John",
        "cypher": "MATCH (u:User {username: 'John'})-[:SENT]->(m:Message) RETURN m ORDER BY m.date DESC"
    },
    {
        "keywords": ["search", "find", "keyword", "term", "contains"],
        "question": "Search messages for 'apple'",
        "cypher": "MATCH (m:Message) WHERE toLower(m.text) CONTAINS 'apple' RETURN m ORDER BY m.date DESC LIMIT 20"
    }
]

def get_examples(question: str) -> list:
    """Returns relevant examples based on keyword matching."""
    q_lower = question.lower()
    relevant = []
    
    for ex in STATIC_EXAMPLES:
        # Check if any keyword matches
        if any(kw in q_lower for kw in ex["keywords"]):
            relevant.append(ex)
            
    # Always include at least one generic example if none matched?
    # Or just return empty list.
    return relevant

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
    },
    {
        "keywords": ["location", "place", "city", "country", "around", "map"],
        "question": "Visualize location names around channels talking about them",
        "cypher": "MATCH (c:Channel)-[:POSTED]->(m:Message)-[:MENTIONS_LOCATION]->(l:Location) RETURN c, m, l LIMIT 100"
    },
    {
        "keywords": ["interaction", "reply", "respond", "who"],
        "question": "Show me user interactions (who replies to whom)",
        "cypher": "MATCH (u1:User)-[:SENT]->(m1:Message)<-[:REPLY_TO]-(m2:Message)<-[:SENT]-(u2:User) RETURN u1, u2, count(*) as interactions ORDER BY interactions DESC LIMIT 50"
    }
]

def get_examples(question: str) -> list:
    """Returns relevant examples based on keyword matching, including user feedback."""
    import json
    import os
    
    q_lower = question.lower()
    relevant = []
    
    # 1. Load Dynamic Feedback
    feedback_examples = []
    # Location of feedback file (persisted via volume mount)
    FEEDBACK_FILE = "/app/feedback.json" 
    
    if os.path.exists(FEEDBACK_FILE):
        try:
            with open(FEEDBACK_FILE, 'r') as f:
                content = f.read()
                if content:
                    feedback_examples = json.loads(content)
        except Exception as e:
            # logging not available here globally, but safe to ignore read errors
            print(f"Error loading feedback: {e}")

    # 2. Combine Sources (Feedback first to give it higher priority in prompt?? Or mixed?)
    # Valid feedback should be prioritized.
    # Structure of feedback: {"question": "...", "cypher": "...", "rating": 1}
    
    # Filter Feedback
    for ex in feedback_examples:
        # Simple similarity: significant word overlap?
        # Or just containment.
        # "keywords" might not exist in feedback, so we generate them or just check query overlap.
        ex_q = ex.get("question", "").lower()
        
        # If the feedback question is very similar to current question, it's a HIT.
        # Simple Jaccard similarity or substring match
        if ex_q in q_lower or q_lower in ex_q:
            relevant.append(ex)
            continue
            
        # Check specific keywords if they exist (calculated during save?)
        # For now, let's just check if common words overlap
        unique_words_query = set(q_lower.split())
        unique_words_ex = set(ex_q.split())
        overlap = unique_words_query.intersection(unique_words_ex)
        # If more than 2 meaningful words overlap (len > 3)
        meaningful_overlap = [w for w in overlap if len(w) > 3]
        if len(meaningful_overlap) >= 2:
            relevant.append(ex)

    # 3. Filter Static Examples
    for ex in STATIC_EXAMPLES:
        # Check if any keyword matches
        if any(kw in q_lower for kw in ex["keywords"]):
            relevant.append(ex)
            
    # Deduplicate by Question
    seen_q = set()
    unique_relevant = []
    for r in relevant:
        if r["question"] not in seen_q:
            unique_relevant.append(r)
            seen_q.add(r["question"])

    return unique_relevant[:5] # Limit to top 5 to save tokens

# backend/app/agents/static_examples.py

STATIC_EXAMPLES = [
    # --- GRAPH EXAMPLES ---
    {
        "keywords": ["reply", "conversation", "discussion", "reply chain", "most replied"],
        "question": "Visualize the reply chain of the most replied-to message",
        "cypher": (
            "MATCH (m:Message)<-[:REPLY_TO]-(reply:Message) "
            "WITH m, count(reply) AS reply_count ORDER BY reply_count DESC LIMIT 1 "
            "MATCH (m)<-[:REPLY_TO*1..5]-(r:Message) "
            "RETURN m, r LIMIT 100"
        )
    },
    {
        "keywords": ["user", "reply", "network", "who replies", "interaction", "respond"],
        "question": "Visualize the network of users who reply to each other",
        "cypher": (
            "MATCH (u1:User)-[:SENT]->(m1:Message)-[:REPLY_TO]->(m2:Message)<-[:SENT]-(u2:User) "
            "WHERE u1 <> u2 "
            "RETURN u1, u2 LIMIT 100"
        )
    },
    {
        "keywords": ["channel", "recommend", "network", "connected channels", "recommendations"],
        "question": "Visualize the graph of channels and their recommended channels",
        "cypher": (
            "MATCH (c1:Channel)-[:RECOMMENDS]->(c2:Channel) "
            "RETURN c1, c2 LIMIT 100"
        )
    },
    {
        "keywords": ["channel", "location", "share", "common location", "channels sharing"],
        "question": "Visualize the graph of channels that share the most locations in common",
        "cypher": (
            "MATCH (c1:Channel)-[:HAS_MESSAGE]->(m1:Message)-[:MENTIONS_LOCATION]->(l:Location)"
            "<-[:MENTIONS_LOCATION]-(m2:Message)<-[:HAS_MESSAGE]-(c2:Channel) "
            "WHERE c1 <> c2 "
            "WITH c1, c2, count(DISTINCT l) AS shared_locations "
            "ORDER BY shared_locations DESC LIMIT 50 "
            "RETURN c1, c2, shared_locations"
        )
    },
    {
        "keywords": ["user", "channel", "shared user", "connected by user", "user overlap"],
        "question": "Visualize channels connected by shared users",
        "cypher": (
            "MATCH (u:User)-[:SENT]->(m1:Message)<-[:HAS_MESSAGE]-(c1:Channel) "
            "MATCH (u)-[:SENT]->(m2:Message)<-[:HAS_MESSAGE]-(c2:Channel) "
            "WHERE c1 <> c2 "
            "WITH c1, c2, count(DISTINCT u) AS shared_users "
            "ORDER BY shared_users DESC LIMIT 40 "
            "RETURN c1, c2, shared_users"
        )
    },
    {
        "keywords": ["emotion", "channel", "negative", "channel emotions", "visualize emotion"],
        "question": "Visualize channels with the most negative emotions and the emotions they express",
        "cypher": (
            "MATCH (c:Channel)-[:HAS_MESSAGE]->(m:Message)-[:HAS_EMOTION]->(e:Emotion) "
            "WHERE e.name CONTAINS 'Hass' OR e.name CONTAINS 'Wut' OR e.name CONTAINS 'Angst' "
            "WITH c, e, count(m) AS cnt ORDER BY cnt DESC LIMIT 200 "
            "RETURN c, e, cnt"
        )
    },
    {
        "keywords": ["politics", "user interaction", "political", "interaction network"],
        "question": "Visualize the user interaction network filtered to messages about politics",
        "cypher": (
            "MATCH (u1:User)-[:SENT]->(m1:Message)-[:REPLY_TO]->(m2:Message)<-[:SENT]-(u2:User) "
            "WHERE u1 <> u2 AND ("
            "  toLower(m1.original_text) CONTAINS 'polit' OR toLower(m1.translated_text) CONTAINS 'polit' OR "
            "  toLower(m2.original_text) CONTAINS 'polit' OR toLower(m2.translated_text) CONTAINS 'polit'"
            ") "
            "RETURN u1, u2 LIMIT 60"
        )
    },

    # --- MAP EXAMPLES ---
    {
        "keywords": ["anger", "fear", "emotion map", "negative map", "anger map", "fear map"],
        "question": "Show map of locations where the most anger or fear was expressed",
        "cypher": (
            "MATCH (m:Message)-[:MENTIONS_LOCATION]->(l:Location) "
            "MATCH (m)-[:HAS_EMOTION]->(e:Emotion) "
            "WHERE (e.name CONTAINS 'Wut' OR e.name CONTAINS 'Angst' OR e.name CONTAINS 'Hass') "
            "WITH l, collect(m)[..3] AS sms, count(m) AS emotion_count "
            "WHERE l.latitude IS NOT NULL AND l.longitude IS NOT NULL "
            "RETURN l.latitude AS lat, l.longitude AS lng, l.canonical_name AS canonical_name, "
            "l.country AS country, l.mention_count AS mention_count, emotion_count, "
            "[msg IN sms | {text: coalesce(msg.translated_text, msg.original_text), date: toString(msg.date)}] AS sample_messages "
            "ORDER BY emotion_count DESC LIMIT 100"
        )
    },
    {
        "keywords": ["ukraine", "keyword map", "map ukraine"],
        "question": "Show map of locations from messages where Ukraine is mentioned",
        "cypher": (
            "MATCH (m:Message)-[:MENTIONS_LOCATION]->(l:Location) "
            "WHERE (toLower(m.original_text) CONTAINS 'ukraine' OR toLower(m.translated_text) CONTAINS 'ukraine') "
            "AND l.latitude IS NOT NULL AND l.longitude IS NOT NULL "
            "WITH l, collect(m)[..3] AS sms "
            "RETURN l.latitude AS lat, l.longitude AS lng, l.canonical_name AS canonical_name, "
            "l.country AS country, l.mention_count AS mention_count, "
            "[msg IN sms | {text: coalesce(msg.translated_text, msg.original_text), date: toString(msg.date)}] AS sample_messages "
            "ORDER BY l.mention_count DESC LIMIT 100"
        )
    },
    {
        "keywords": ["propaganda", "channel propaganda", "map propaganda"],
        "question": "Show map of locations mentioned by channels with the most propaganda content",
        "cypher": (
            "MATCH (c:Channel)-[:HAS_MESSAGE]->(m:Message)-[:HAS_CLASSIFICATION]->(cl:Classification) "
            "WHERE toLower(cl.name) CONTAINS 'propaganda' "
            "WITH DISTINCT c "
            "MATCH (c)-[:HAS_MESSAGE]->(m2:Message)-[:MENTIONS_LOCATION]->(l:Location) "
            "WHERE l.latitude IS NOT NULL AND l.longitude IS NOT NULL "
            "WITH l, collect(m2)[..3] AS sms "
            "RETURN l.latitude AS lat, l.longitude AS lng, l.canonical_name AS canonical_name, "
            "l.country AS country, l.mention_count AS mention_count, "
            "[msg IN sms | {text: coalesce(msg.translated_text, msg.original_text), date: toString(msg.date)}] AS sample_messages "
            "ORDER BY l.mention_count DESC LIMIT 100"
        )
    },
    {
        "keywords": ["negative emotion", "negative map", "map negative"],
        "question": "Show map of locations from messages with negative emotions only",
        "cypher": (
            "MATCH (m:Message)-[:MENTIONS_LOCATION]->(l:Location) "
            "MATCH (m)-[:HAS_EMOTION]->(e:Emotion) "
            "WHERE (e.name CONTAINS 'Hass' OR e.name CONTAINS 'Wut' OR e.name CONTAINS 'Angst' "
            "OR e.name CONTAINS 'Verzweiflung' OR e.name CONTAINS 'Misstrauen') "
            "AND l.latitude IS NOT NULL AND l.longitude IS NOT NULL "
            "WITH l, collect(m)[..3] AS sms "
            "RETURN l.latitude AS lat, l.longitude AS lng, l.canonical_name AS canonical_name, "
            "l.country AS country, l.mention_count AS mention_count, "
            "[msg IN sms | {text: coalesce(msg.translated_text, msg.original_text), date: toString(msg.date)}] AS sample_messages "
            "ORDER BY l.mention_count DESC LIMIT 100"
        )
    },

    # --- CHART / STATS EXAMPLES ---
    {
        "keywords": ["message volume", "messages over time", "last 30 days", "last year", "trend", "timeline"],
        "question": "Show message volume over the last 30 days",
        "cypher": (
            "MATCH (m:Message) "
            "WHERE m.date >= datetime() - duration({days: 30}) "
            "RETURN toString(date(m.date)) AS day, count(m) AS messages "
            "ORDER BY day"
        )
    },
    {
        "keywords": ["category", "classification", "categories", "common categories", "topic distribution"],
        "question": "What are the most common message categories across all channels?",
        "cypher": (
            "MATCH (m:Message)-[:HAS_CLASSIFICATION]->(cl:Classification) "
            "RETURN cl.name AS category, count(m) AS count "
            "ORDER BY count DESC LIMIT 20"
        )
    },
    {
        "keywords": ["gewalt", "bedrohung", "violence", "threat", "classified as"],
        "question": "Which channels have the most messages classified as Gewalt or Bedrohung?",
        "cypher": (
            "MATCH (c:Channel)-[:HAS_MESSAGE]->(m:Message)-[:HAS_CLASSIFICATION]->(cl:Classification) "
            "WHERE toLower(cl.name) CONTAINS 'gewalt' OR toLower(cl.name) CONTAINS 'bedrohung' "
            "RETURN c.username AS channel, count(m) AS count "
            "ORDER BY count DESC LIMIT 20"
        )
    },
    {
        "keywords": ["emotion distribution", "emotion per channel", "emotion chart", "emotion breakdown"],
        "question": "Show the distribution of emotions per channel as a chart",
        "cypher": (
            "MATCH (c:Channel)-[:HAS_MESSAGE]->(m:Message)-[:HAS_EMOTION]->(e:Emotion) "
            "RETURN c.username AS channel, e.name AS emotion, count(m) AS cnt "
            "ORDER BY cnt DESC LIMIT 100"
        )
    },
    {
        "keywords": ["dominant emotion", "most common emotion", "overall emotion", "emotion across"],
        "question": "What are the dominant emotions across all messages?",
        "cypher": (
            "MATCH (m:Message)-[:HAS_EMOTION]->(e:Emotion) "
            "RETURN e.name AS emotion, count(m) AS count "
            "ORDER BY count DESC"
        )
    },
    {
        "keywords": ["top location", "most mentioned location", "top 15 location", "frequent location"],
        "question": "What are the top 15 most mentioned locations?",
        "cypher": (
            "MATCH (m:Message)-[:MENTIONS_LOCATION]->(l:Location) "
            "RETURN l.canonical_name AS location, l.country AS country, count(m) AS mentions "
            "ORDER BY mentions DESC LIMIT 15"
        )
    },
    {
        "keywords": ["active channel", "most active", "channel message count", "channel activity"],
        "question": "Which channels are most active by message count?",
        "cypher": (
            "MATCH (c:Channel)-[:HAS_MESSAGE]->(m:Message) "
            "RETURN c.username AS channel, count(m) AS messages "
            "ORDER BY messages DESC LIMIT 20"
        )
    },
    {
        "keywords": ["active sender", "most active user", "top sender", "who sends most"],
        "question": "Who are the most active senders across all channels?",
        "cypher": (
            "MATCH (u:User)-[:SENT]->(m:Message) "
            "RETURN coalesce(u.username, u.first_name) AS sender, count(m) AS messages "
            "ORDER BY messages DESC LIMIT 20"
        )
    },
    {
        "keywords": ["total messages", "how many messages", "message count", "scraped"],
        "question": "How many messages have been scraped in total?",
        "cypher": "MATCH (m:Message) RETURN count(m) AS total_messages"
    },
    {
        "keywords": ["search", "find", "keyword", "term", "contains"],
        "question": "Search messages containing 'apple'",
        "cypher": (
            "MATCH (m:Message) "
            "WHERE (toLower(m.original_text) CONTAINS 'apple' OR toLower(m.translated_text) CONTAINS 'apple') "
            "RETURN m ORDER BY m.date DESC LIMIT 20"
        )
    },
    {
        "keywords": ["thread", "reply thread", "show thread"],
        "question": "Show me the thread starting with message 123",
        "cypher": (
            "MATCH (root:Message {mid: '123'})<-[:REPLY_TO*0..5]-(reply:Message) "
            "RETURN root, reply ORDER BY reply.date ASC"
        )
    },
]


def get_examples(question: str) -> list:
    """Returns relevant examples based on keyword matching, including user feedback."""
    import json
    import os

    q_lower = question.lower()
    relevant = []

    # 1. Load Dynamic Feedback
    feedback_examples = []
    FEEDBACK_FILE = "/app/feedback.json"

    if os.path.exists(FEEDBACK_FILE):
        try:
            with open(FEEDBACK_FILE, 'r') as f:
                content = f.read()
                if content:
                    feedback_examples = json.loads(content)
        except Exception as e:
            print(f"Error loading feedback: {e}")

    # 2. Filter Feedback (exact/near match)
    for ex in feedback_examples:
        ex_q = ex.get("question", "").lower()
        if ex_q in q_lower or q_lower in ex_q:
            relevant.append(ex)
            continue
        unique_words_query = set(q_lower.split())
        unique_words_ex = set(ex_q.split())
        overlap = unique_words_query.intersection(unique_words_ex)
        meaningful_overlap = [w for w in overlap if len(w) > 3]
        if len(meaningful_overlap) >= 2:
            relevant.append(ex)

    # 3. Filter Static Examples by keyword
    for ex in STATIC_EXAMPLES:
        if any(kw in q_lower for kw in ex["keywords"]):
            relevant.append(ex)

    # Deduplicate by Question
    seen_q = set()
    unique_relevant = []
    for r in relevant:
        if r["question"] not in seen_q:
            unique_relevant.append(r)
            seen_q.add(r["question"])

    return unique_relevant[:5]  # Limit to top 5 to save tokens

-- RAG-spezifische Tabellen erstellen

-- Message Embeddings Tabelle
CREATE TABLE IF NOT EXISTS message_embeddings (
    id SERIAL PRIMARY KEY,
    neo4j_message_id VARCHAR(255) UNIQUE NOT NULL,
    case_id INTEGER REFERENCES casefiles(id) ON DELETE CASCADE,
    channel_name VARCHAR(255) NOT NULL,
    
    -- Vector embedding (384 dimensions für multilingual-MiniLM)
    embedding vector(384) NOT NULL,
    
    -- Metadaten für bessere Suche
    message_timestamp TIMESTAMP NOT NULL,
    message_length INTEGER,
    language VARCHAR(5) DEFAULT 'unknown',
    
    -- Tracking
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Message Analysen Tabelle
CREATE TABLE IF NOT EXISTS message_analyses (
    id SERIAL PRIMARY KEY,
    neo4j_message_id VARCHAR(255) UNIQUE NOT NULL,
    case_id INTEGER REFERENCES casefiles(id) ON DELETE CASCADE,
    
    -- Sentiment Analysis
    sentiment_score FLOAT CHECK (sentiment_score >= -1 AND sentiment_score <= 1),
    sentiment_label VARCHAR(20) CHECK (sentiment_label IN ('positive', 'neutral', 'negative')),
    sentiment_confidence FLOAT CHECK (sentiment_confidence >= 0 AND sentiment_confidence <= 1),
    
    -- Topic Analysis
    topics TEXT[] DEFAULT '{}',
    topic_scores JSONB DEFAULT '{}',
    
    -- Named Entity Recognition
    entities JSONB DEFAULT '{}',
    
    -- Risk Assessment
    risk_score FLOAT CHECK (risk_score >= 0 AND risk_score <= 1),
    risk_categories TEXT[] DEFAULT '{}',
    risk_reasoning TEXT,
    
    -- Analysis Metadata
    model_used VARCHAR(100) NOT NULL,
    analysis_confidence FLOAT CHECK (analysis_confidence >= 0 AND analysis_confidence <= 1),
    processing_time_ms INTEGER,
    
    -- Tracking
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- RAG Query History (für Analytics/Debugging)
CREATE TABLE IF NOT EXISTS rag_queries (
    id SERIAL PRIMARY KEY,
    case_id INTEGER REFERENCES casefiles(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    
    query_text TEXT NOT NULL,
    query_embedding vector(384),
    
    -- Results Metadata
    results_count INTEGER DEFAULT 0,
    avg_similarity_score FLOAT,
    llm_response TEXT,
    
    -- Performance Metrics
    embedding_time_ms INTEGER,
    search_time_ms INTEGER,
    llm_time_ms INTEGER,
    total_time_ms INTEGER,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indizes für Performance
CREATE INDEX IF NOT EXISTS idx_message_embeddings_case_id 
    ON message_embeddings(case_id);

CREATE INDEX IF NOT EXISTS idx_message_embeddings_channel 
    ON message_embeddings(case_id, channel_name);

CREATE INDEX IF NOT EXISTS idx_message_embeddings_timestamp 
    ON message_embeddings(message_timestamp DESC);

-- Vector Index für Similarity Search (IVFFlat)
CREATE INDEX IF NOT EXISTS idx_message_embeddings_vector 
    ON message_embeddings 
    USING ivfflat (embedding vector_cosine_ops) 
    WITH (lists = 100);

-- Alternativ: HNSW Index (besser für kleinere Datasets)
-- CREATE INDEX IF NOT EXISTS idx_message_embeddings_vector_hnsw 
--     ON message_embeddings 
--     USING hnsw (embedding vector_cosine_ops) 
--     WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_message_analyses_case_id 
    ON message_analyses(case_id);

CREATE INDEX IF NOT EXISTS idx_message_analyses_risk_score 
    ON message_analyses(case_id, risk_score DESC) 
    WHERE risk_score > 0.5;

CREATE INDEX IF NOT EXISTS idx_message_analyses_sentiment 
    ON message_analyses(case_id, sentiment_score);

CREATE INDEX IF NOT EXISTS idx_rag_queries_case_user 
    ON rag_queries(case_id, user_id);

-- Trigger für updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_message_embeddings_updated_at 
    BEFORE UPDATE ON message_embeddings 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_message_analyses_updated_at 
    BEFORE UPDATE ON message_analyses 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Views für häufige Queries
CREATE OR REPLACE VIEW message_embeddings_with_analysis AS
SELECT 
    e.*,
    a.sentiment_score,
    a.sentiment_label,
    a.topics,
    a.risk_score,
    a.model_used as analysis_model
FROM message_embeddings e
LEFT JOIN message_analyses a ON e.neo4j_message_id = a.neo4j_message_id;

-- Funktionen für Vector Operations
CREATE OR REPLACE FUNCTION find_similar_messages(
    query_embedding vector(384),
    target_case_id integer,
    similarity_threshold float DEFAULT 0.7,
    result_limit integer DEFAULT 10
)
RETURNS TABLE (
    neo4j_message_id varchar(255),
    channel_name varchar(255),
    similarity_score float,
    message_timestamp timestamp
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.neo4j_message_id,
        e.channel_name,
        1 - (e.embedding <=> query_embedding) as similarity_score,
        e.message_timestamp
    FROM message_embeddings e
    WHERE e.case_id = target_case_id
        AND 1 - (e.embedding <=> query_embedding) >= similarity_threshold
    ORDER BY e.embedding <=> query_embedding
    LIMIT result_limit;
END;
$$ LANGUAGE plpgsql;

-- Statistik-Funktionen
CREATE OR REPLACE FUNCTION get_case_analysis_stats(target_case_id integer)
RETURNS TABLE (
    total_messages bigint,
    analyzed_messages bigint,
    avg_sentiment float,
    high_risk_messages bigint,
    top_topics jsonb
) AS $$
BEGIN
    RETURN QUERY
    WITH stats AS (
        SELECT 
            COUNT(e.id) as total_msg,
            COUNT(a.id) as analyzed_msg,
            AVG(a.sentiment_score) as avg_sent,
            COUNT(CASE WHEN a.risk_score > 0.7 THEN 1 END) as high_risk,
            array_agg(DISTINCT topic) FILTER (WHERE topic IS NOT NULL) as all_topics
        FROM message_embeddings e
        LEFT JOIN message_analyses a ON e.neo4j_message_id = a.neo4j_message_id
        LEFT JOIN LATERAL unnest(a.topics) as topic ON true
        WHERE e.case_id = target_case_id
    ),
    topic_counts AS (
        SELECT jsonb_object_agg(topic, cnt) as topic_json
        FROM (
            SELECT topic, COUNT(*) as cnt
            FROM stats, unnest(all_topics) as topic
            GROUP BY topic
            ORDER BY cnt DESC
            LIMIT 10
        ) t
    )
    SELECT 
        s.total_msg,
        s.analyzed_msg,
        s.avg_sent,
        s.high_risk,
        COALESCE(tc.topic_json, '{}'::jsonb)
    FROM stats s
    CROSS JOIN topic_counts tc;
END;
$$ LANGUAGE plpgsql;

\echo 'RAG tables and functions successfully created'
-- pgvector Extension für RAG-Features aktivieren
CREATE EXTENSION IF NOT EXISTS vector;

-- Test: Vector Extension verfügbar
SELECT extname FROM pg_extension WHERE extname = 'vector';

-- Info ausgeben
\echo 'pgvector extension successfully installed'
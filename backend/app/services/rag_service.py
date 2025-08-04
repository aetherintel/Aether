# services/rag_service.py
import os
import json
import base64
import asyncio
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import numpy as np

import openai
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
from sqlalchemy import text, func
import asyncpg

from services.neo4j_backend_client import (
    get_case_channels_with_recommendations,
    get_total_message_count_for_channels,
    get_messages_with_media
)
from controller.casefile_controller import SessionLocal, MessageEmbedding, MessageAnalysis

class RAGService:
    def __init__(self, db_session: Optional[Session] = None):
        # OpenAI Client
        self.openai_client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Database
        self.db = db_session or SessionLocal()
        
        # Neo4j Client (Ihr bestehender)
        
        # PostgreSQL connection für Vector operations
        self.pg_pool = None
    
    async def initialize_pg_pool(self):
        """Initialize PostgreSQL connection pool for vector operations"""
        if not self.pg_pool:
            DATABASE_URL = os.getenv("DB_URL")  # Ihre bestehende DB URL
            self.pg_pool = await asyncpg.create_pool(DATABASE_URL)
    
    async def create_text_embedding(self, text: str) -> List[float]:
        """Erstellt Embedding mit OpenAI text-embedding-3-large"""
        try:
            response = await self.openai_client.embeddings.create(
                model="text-embedding-3-large",
                input=text,
                encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error creating embedding: {e}")
            return []
    
    async def analyze_text_with_gpt(self, text: str, context: Dict = None) -> Dict:
        """Analysiert Text mit GPT-4o-mini"""
        context_info = ""
        if context:
            context_info = f"Channel: {context.get('channel', 'unknown')}, Case: {context.get('case_id', 'unknown')}"
        
        system_prompt = """Du bist ein OSINT-Analyst. Analysiere den folgenden Text und gib eine strukturierte JSON-Antwort zurück mit:
        {
            "sentiment_score": float (-1 bis 1),
            "sentiment_label": "positive" | "neutral" | "negative",
            "topics": ["topic1", "topic2", ...] (max 5),
            "entities": {
                "persons": ["person1", ...],
                "organizations": ["org1", ...],
                "locations": ["location1", ...]
            },
            "risk_score": float (0 bis 1),
            "risk_categories": ["category1", ...],
            "language": "de" | "en" | "other",
            "summary": "Kurze Zusammenfassung (max 100 Zeichen)"
        }
        
        Antworte NUR mit gültigem JSON, ohne zusätzlichen Text."""
        
        user_prompt = f"Kontext: {context_info}\n\nText: {text}"
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=800
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception as e:
            print(f"Error analyzing text: {e}")
            return {
                "sentiment_score": 0.0,
                "sentiment_label": "neutral",
                "topics": [],
                "entities": {"persons": [], "organizations": [], "locations": []},
                "risk_score": 0.0,
                "risk_categories": [],
                "language": "unknown",
                "summary": "Analysis failed"
            }
    
    async def analyze_image_with_gpt(self, image_path: str, context_text: str = "") -> Dict:
        """Analysiert Bild mit GPT-4o Vision"""
        try:
            # Bild zu base64 konvertieren
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            system_prompt = """Du bist ein OSINT-Analyst. Analysiere das Bild und gib eine strukturierte JSON-Antwort zurück:
            {
                "description": "Objektive Beschreibung des Bildinhalts",
                "detected_text": "Text im Bild (falls vorhanden)",
                "symbols_logos": ["symbol1", "logo1", ...],
                "sentiment_score": float (-1 bis 1),
                "risk_score": float (0 bis 1),
                "risk_categories": ["category1", ...],
                "content_type": "photo" | "screenshot" | "meme" | "document" | "other",
                "summary": "Kurze Zusammenfassung (max 100 Zeichen)"
            }
            
            Antworte NUR mit gültigem JSON."""
            
            user_prompt = f"Kontext: {context_text}\n\nAnalysiere dieses Bild für eine OSINT-Untersuchung:"
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception as e:
            print(f"Error analyzing image: {e}")
            return {
                "description": "Image analysis failed",
                "detected_text": "",
                "symbols_logos": [],
                "sentiment_score": 0.0,
                "risk_score": 0.0,
                "risk_categories": [],
                "content_type": "other",
                "summary": "Analysis failed"
            }
    
    async def process_message(self, neo4j_message_id: str, case_id: int) -> Dict:
        """Verarbeitet eine Message vollständig: Embedding + Analyse"""
        
        # 1. Message aus Neo4j laden
        message_data = await self.neo4j.get_message_by_id(neo4j_message_id)
        if not message_data:
            return {"error": f"Message {neo4j_message_id} not found in Neo4j"}
        
        text = message_data.get("text", "")
        media_path = message_data.get("media_path")
        channel = message_data.get("channel", "unknown")
        timestamp = message_data.get("timestamp", datetime.now())
        
        result = {
            "neo4j_message_id": neo4j_message_id,
            "case_id": case_id,
            "processing_steps": []
        }
        
        # 2. Text verarbeiten (falls vorhanden)
        text_embedding = None
        text_analysis = None
        
        if text and text.strip():
            result["processing_steps"].append("text_processing")
            
            # Text Embedding erstellen
            text_embedding = await self.create_text_embedding(text)
            
            # Text analysieren
            text_analysis = await self.analyze_text_with_gpt(
                text, 
                {"channel": channel, "case_id": case_id}
            )
        
        # 3. Bild verarbeiten (falls vorhanden)
        image_analysis = None
        image_description_embedding = None
        
        if media_path and os.path.exists(media_path):
            result["processing_steps"].append("image_processing")
            
            # Bild analysieren
            image_analysis = await self.analyze_image_with_gpt(media_path, text or "")
            
            # Embedding aus Bildbeschreibung erstellen
            if image_analysis.get("description"):
                image_description_embedding = await self.create_text_embedding(
                    image_analysis["description"]
                )
        
        # 4. Kombiniertes Embedding erstellen
        combined_embedding = None
        if text_embedding and image_description_embedding:
            # Gewichteter Durchschnitt (70% Text, 30% Bild)
            text_array = np.array(text_embedding)
            image_array = np.array(image_description_embedding)
            combined_array = 0.7 * text_array + 0.3 * image_array
            combined_embedding = combined_array.tolist()
        elif text_embedding:
            combined_embedding = text_embedding
        elif image_description_embedding:
            combined_embedding = image_description_embedding
        
        # 5. In PostgreSQL speichern
        if combined_embedding:
            await self.store_embeddings_and_analysis(
                neo4j_message_id=neo4j_message_id,
                case_id=case_id,
                channel_name=channel,
                message_timestamp=timestamp,
                text_embedding=text_embedding,
                image_description_embedding=image_description_embedding,
                combined_embedding=combined_embedding,
                text_analysis=text_analysis,
                image_analysis=image_analysis,
                has_text=bool(text),
                has_image=bool(media_path)
            )
            result["processing_steps"].append("storage_complete")
        
        return result
    
    async def store_embeddings_and_analysis(
        self,
        neo4j_message_id: str,
        case_id: int,
        channel_name: str,
        message_timestamp: datetime,
        text_embedding: Optional[List[float]] = None,
        image_description_embedding: Optional[List[float]] = None,
        combined_embedding: Optional[List[float]] = None,
        text_analysis: Optional[Dict] = None,
        image_analysis: Optional[Dict] = None,
        has_text: bool = False,
        has_image: bool = False
    ):
        """Speichert Embeddings und Analysen in PostgreSQL"""
        
        await self.initialize_pg_pool()
        
        # SQL für UPSERT (ON CONFLICT UPDATE)
        upsert_sql = """
        INSERT INTO message_embeddings (
            neo4j_message_id, case_id, channel_name, message_timestamp,
            text_embedding, image_description_embedding, combined_embedding,
            has_text, has_image, text_analysis, image_analysis, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
        ON CONFLICT (neo4j_message_id) 
        DO UPDATE SET
            text_embedding = EXCLUDED.text_embedding,
            image_description_embedding = EXCLUDED.image_description_embedding,
            combined_embedding = EXCLUDED.combined_embedding,
            has_text = EXCLUDED.has_text,
            has_image = EXCLUDED.has_image,
            text_analysis = EXCLUDED.text_analysis,
            image_analysis = EXCLUDED.image_analysis,
            updated_at = NOW()
        """
        
        async with self.pg_pool.acquire() as conn:
            await conn.execute(
                upsert_sql,
                neo4j_message_id,
                case_id,
                channel_name,
                message_timestamp,
                text_embedding,
                image_description_embedding,
                combined_embedding,
                has_text,
                has_image,
                json.dumps(text_analysis) if text_analysis else None,
                json.dumps(image_analysis) if image_analysis else None
            )
    
    async def semantic_search(
        self,
        query: str,
        case_id: int,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict]:
        """Semantische Suche mit pgvector"""
        
        # Query Embedding erstellen
        query_embedding = await self.create_text_embedding(query)
        if not query_embedding:
            return []
        
        await self.initialize_pg_pool()
        
        # Vector Search SQL
        search_sql = """
        SELECT 
            neo4j_message_id,
            channel_name,
            1 - (combined_embedding <=> $1::vector(3072)) as similarity_score,
            has_text,
            has_image,
            message_timestamp,
            text_analysis,
            image_analysis
        FROM message_embeddings
        WHERE case_id = $2
            AND combined_embedding IS NOT NULL
            AND 1 - (combined_embedding <=> $1::vector(3072)) >= $3
        ORDER BY combined_embedding <=> $1::vector(3072)
        LIMIT $4
        """
        
        results = []
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch(
                search_sql,
                query_embedding,
                case_id,
                similarity_threshold,
                limit
            )
            
            for row in rows:
                # Message-Details aus Neo4j laden
                message_data = await self.neo4j.get_message_by_id(row["neo4j_message_id"])
                
                result_item = {
                    "neo4j_message_id": row["neo4j_message_id"],
                    "channel_name": row["channel_name"],
                    "similarity_score": float(row["similarity_score"]),
                    "has_text": row["has_text"],
                    "has_image": row["has_image"],
                    "message_timestamp": row["message_timestamp"],
                    "message_data": message_data,
                    "text_analysis": json.loads(row["text_analysis"]) if row["text_analysis"] else None,
                    "image_analysis": json.loads(row["image_analysis"]) if row["image_analysis"] else None
                }
                results.append(result_item)
        
        return results
    
    async def get_case_statistics(self, case_id: int) -> Dict:
        """Statistiken für einen Case"""
        await self.initialize_pg_pool()
        
        stats_sql = """
        SELECT 
            COUNT(*) as total_messages,
            COUNT(*) FILTER (WHERE has_text) as text_messages,
            COUNT(*) FILTER (WHERE has_image) as image_messages,
            AVG((text_analysis->>'sentiment_score')::float) as avg_sentiment,
            COUNT(*) FILTER (WHERE (text_analysis->>'risk_score')::float > 0.7) as high_risk_messages
        FROM message_embeddings
        WHERE case_id = $1
        """
        
        async with self.pg_pool.acquire() as conn:
            row = await conn.fetchrow(stats_sql, case_id)
            
            return {
                "total_messages": row["total_messages"] or 0,
                "text_messages": row["text_messages"] or 0,
                "image_messages": row["image_messages"] or 0,
                "avg_sentiment": float(row["avg_sentiment"]) if row["avg_sentiment"] else 0.0,
                "high_risk_messages": row["high_risk_messages"] or 0
            }
    
    async def process_case_batch(self, case_id: int, max_messages: int = 100) -> Dict:
        """Verarbeitet alle unprocessed Messages eines Cases"""
        
        # Alle Messages aus Neo4j für diesen Case holen
        case_messages = await self.neo4j.get_case_messages(case_id, limit=max_messages)
        
        # Bereits verarbeitete Messages checken
        await self.initialize_pg_pool()
        async with self.pg_pool.acquire() as conn:
            processed_ids = await conn.fetch(
                "SELECT neo4j_message_id FROM message_embeddings WHERE case_id = $1",
                case_id
            )
            processed_set = {row["neo4j_message_id"] for row in processed_ids}
        
        # Unverarbeitete Messages filtern
        unprocessed_messages = [
            msg for msg in case_messages 
            if msg["id"] not in processed_set
        ]
        
        results = {
            "case_id": case_id,
            "total_messages": len(case_messages),
            "already_processed": len(processed_set),
            "to_process": len(unprocessed_messages),
            "processed_now": 0,
            "errors": []
        }
        
        # Messages verarbeiten
        for message in unprocessed_messages[:max_messages]:
            try:
                await self.process_message(message["id"], case_id)
                results["processed_now"] += 1
                
                # Rate limiting für OpenAI API
                await asyncio.sleep(0.1)
                
            except Exception as e:
                error_info = {
                    "message_id": message["id"],
                    "error": str(e)
                }
                results["errors"].append(error_info)
                print(f"Error processing message {message['id']}: {e}")
        
        return results
    
    def close(self):
        """Cleanup resources"""
        if self.db:
            self.db.close()
        if self.pg_pool:
            asyncio.create_task(self.pg_pool.close())


# Background Task Funktionen für FastAPI
async def process_case_messages_background(case_id: int):
    """Background Task für Case-Processing"""
    rag_service = RAGService()
    try:
        result = await rag_service.process_case_batch(case_id, max_messages=100)
        print(f"Batch processing completed for case {case_id}: {result}")
    except Exception as e:
        print(f"Background processing failed for case {case_id}: {e}")
    finally:
        rag_service.close()


# Convenience Functions
async def quick_search(query: str, case_id: int, limit: int = 5) -> List[Dict]:
    """Quick semantic search function"""
    rag_service = RAGService()
    try:
        results = await rag_service.semantic_search(query, case_id, limit)
        return results
    finally:
        rag_service.close()


async def analyze_single_message(neo4j_message_id: str, case_id: int) -> Dict:
    """Analyze a single message"""
    rag_service = RAGService()
    try:
        result = await rag_service.process_message(neo4j_message_id, case_id)
        return result
    finally:
        rag_service.close()
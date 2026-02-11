#!/usr/bin/env python3
"""
Neo4j Schema Migration: Complex → Simplified

This script migrates the existing complex schema to a simplified version
optimized for LLM text-to-cypher generation.

Phase 1: Add new properties (non-breaking)
Phase 2: Backfill data from old structure
Phase 3: Validate migration
"""

import asyncio
import os
from pathlib import Path
from neo4j import AsyncGraphDatabase
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env.dev
BASE_DIR = Path(__file__).parent.parent
env_file = BASE_DIR / '.env.dev'
if env_file.exists():
    logger.info(f"Loading environment from {env_file}")
    load_dotenv(env_file)
else:
    logger.warning(f"No .env.dev file found at {env_file}, using environment variables")


class SchemaMigrator:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self):
        await self.driver.close()

    async def phase1_add_new_properties(self):
        """
        Phase 1: Add new simplified properties alongside existing ones
        This is NON-BREAKING - old system continues to work
        """
        logger.info("Phase 1: Adding new simplified properties to Message nodes")

        cypher = """
        MATCH (m:Message)
        WHERE m.text IS NULL  // Only update if not already migrated

        // Build unified 'text' field (best available text)
        WITH m,
             coalesce(
                m.translated_text,
                m.original_text,
                m.image_text_translated,
                m.image_text,
                m.audio_text_translated,
                m.audio_text,
                ''
             ) as unified_text,

             // Build unified 'language' field
             coalesce(
                m.original_language,
                m.image_detected_language,
                m.audio_language,
                'unknown'
             ) as unified_language

        SET m.text = unified_text,
            m.language = unified_language,
            m.emotions = [],
            m.classifications = [],
            m.location_names = []

        RETURN count(m) as updated_count
        """

        async with self.driver.session() as session:
            result = await session.run(cypher)
            record = await result.single()
            count = record["updated_count"] if record else 0
            logger.info(f"✅ Updated {count} Message nodes with new properties")

    async def phase2_backfill_emotions(self):
        """
        Phase 2a: Migrate Emotion relationships to array property
        """
        logger.info("Phase 2a: Backfilling emotions from relationships to array")

        cypher = """
        MATCH (m:Message)-[r:HAS_EMOTION]->(e:Emotion)
        WHERE size(m.emotions) = 0  // Only if not already backfilled

        WITH m, collect(DISTINCT e.name) as emotion_list
        SET m.emotions = emotion_list

        RETURN count(m) as updated_count
        """

        async with self.driver.session() as session:
            result = await session.run(cypher)
            record = await result.single()
            count = record["updated_count"] if record else 0
            logger.info(f"✅ Backfilled emotions for {count} messages")

    async def phase2_backfill_classifications(self):
        """
        Phase 2b: Migrate Classification relationships to array property
        """
        logger.info("Phase 2b: Backfilling classifications from relationships to array")

        cypher = """
        MATCH (m:Message)-[r:HAS_CLASSIFICATION]->(c:Classification)
        WHERE size(m.classifications) = 0  // Only if not already backfilled

        WITH m, collect(DISTINCT c.name) as classification_list
        SET m.classifications = classification_list

        RETURN count(m) as updated_count
        """

        async with self.driver.session() as session:
            result = await session.run(cypher)
            record = await result.single()
            count = record["updated_count"] if record else 0
            logger.info(f"✅ Backfilled classifications for {count} messages")

    async def phase2_backfill_locations(self):
        """
        Phase 2c: Add location_names array for quick filtering
        (Keep MENTIONS_LOCATION relationships for geospatial queries)
        """
        logger.info("Phase 2c: Backfilling location names to array")

        cypher = """
        MATCH (m:Message)-[:MENTIONS_LOCATION]->(l:Location)
        WHERE size(m.location_names) = 0  // Only if not already backfilled

        WITH m, collect(DISTINCT l.canonical_name) as location_list
        SET m.location_names = location_list

        RETURN count(m) as updated_count
        """

        async with self.driver.session() as session:
            result = await session.run(cypher)
            record = await result.single()
            count = record["updated_count"] if record else 0
            logger.info(f"✅ Backfilled location names for {count} messages")

    async def validate_migration(self):
        """
        Validate that migration was successful
        """
        logger.info("Validating migration...")

        validations = {
            "Messages with text property": """
                MATCH (m:Message)
                WHERE m.text IS NOT NULL AND m.text <> ''
                RETURN count(m) as count
            """,

            "Messages with emotions": """
                MATCH (m:Message)
                WHERE size(m.emotions) > 0
                RETURN count(m) as count
            """,

            "Messages with classifications": """
                MATCH (m:Message)
                WHERE size(m.classifications) > 0
                RETURN count(m) as count
            """,

            "Messages with location_names": """
                MATCH (m:Message)
                WHERE size(m.location_names) > 0
                RETURN count(m) as count
            """,

            "Total Messages": """
                MATCH (m:Message)
                RETURN count(m) as count
            """
        }

        results = {}
        async with self.driver.session() as session:
            for label, query in validations.items():
                result = await session.run(query)
                record = await result.single()
                results[label] = record["count"] if record else 0

        logger.info("\n📊 Migration Validation Results:")
        logger.info("=" * 50)
        for label, count in results.items():
            logger.info(f"{label}: {count}")
        logger.info("=" * 50)

        # Calculate percentages
        total = results["Total Messages"]
        if total > 0:
            logger.info(f"\nCoverage:")
            logger.info(f"  Text populated: {results['Messages with text property']/total*100:.1f}%")
            logger.info(f"  Emotions: {results['Messages with emotions']/total*100:.1f}%")
            logger.info(f"  Classifications: {results['Messages with classifications']/total*100:.1f}%")
            logger.info(f"  Locations: {results['Messages with location_names']/total*100:.1f}%")

    async def create_indexes(self):
        """
        Create indexes for new properties to ensure good query performance
        """
        logger.info("Creating indexes for new properties...")

        indexes = [
            "CREATE INDEX message_text_idx IF NOT EXISTS FOR (m:Message) ON (m.text)",
            "CREATE INDEX message_language_idx IF NOT EXISTS FOR (m:Message) ON (m.language)",
            "CREATE INDEX message_emotions_idx IF NOT EXISTS FOR (m:Message) ON (m.emotions)",
            "CREATE INDEX message_classifications_idx IF NOT EXISTS FOR (m:Message) ON (m.classifications)",
        ]

        async with self.driver.session() as session:
            for index_query in indexes:
                try:
                    await session.run(index_query)
                    logger.info(f"✅ Created index: {index_query.split('FOR')[0]}")
                except Exception as e:
                    logger.warning(f"Index creation skipped: {e}")

    async def sample_comparison_queries(self):
        """
        Run sample queries to compare old vs new approach
        """
        logger.info("\n🔍 Sample Query Comparison:")
        logger.info("=" * 50)

        # Old way: Complex emotion query
        logger.info("\nOLD WAY - Find messages with 'angry' emotion:")
        old_query = """
        MATCH (m:Message)-[:HAS_EMOTION]->(e:Emotion)
        WHERE e.name = 'angry'
        RETURN count(m) as count
        """

        # New way: Simple array filter
        logger.info("NEW WAY - Find messages with 'angry' emotion:")
        new_query = """
        MATCH (m:Message)
        WHERE 'angry' IN m.emotions
        RETURN count(m) as count
        """

        async with self.driver.session() as session:
            # Time old query
            import time
            start = time.time()
            result_old = await session.run(old_query)
            record_old = await result_old.single()
            time_old = time.time() - start
            count_old = record_old["count"] if record_old else 0

            # Time new query
            start = time.time()
            result_new = await session.run(new_query)
            record_new = await result_new.single()
            time_new = time.time() - start
            count_new = record_new["count"] if record_new else 0

            logger.info(f"\nResults:")
            logger.info(f"  Old approach: {count_old} messages in {time_old*1000:.2f}ms")
            logger.info(f"  New approach: {count_new} messages in {time_new*1000:.2f}ms")
            logger.info(f"  Speedup: {time_old/time_new:.2f}x faster" if time_new > 0 else "N/A")

    async def run_full_migration(self):
        """
        Run all migration phases
        """
        logger.info("🚀 Starting Neo4j Schema Migration")
        logger.info("=" * 50)

        try:
            # Phase 1: Add new properties
            await self.phase1_add_new_properties()

            # Phase 2: Backfill data
            await self.phase2_backfill_emotions()
            await self.phase2_backfill_classifications()
            await self.phase2_backfill_locations()

            # Create indexes
            await self.create_indexes()

            # Validate
            await self.validate_migration()

            # Sample queries
            await self.sample_comparison_queries()

            logger.info("\n✅ Migration completed successfully!")
            logger.info("\nNext steps:")
            logger.info("1. Update worker services to write to new properties")
            logger.info("2. Update repository queries to use new properties")
            logger.info("3. Test LLM with simplified schema")
            logger.info("4. Once validated, remove old properties in Phase 3")

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}", exc_info=True)
            raise


async def main():
    # Load from environment or use defaults
    # Replace Docker hostname 'neo4j' with 'localhost' for local execution
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    if "neo4j:" in uri:
        uri = uri.replace("neo4j:", "localhost:")
        logger.info(f"Replaced Docker hostname with localhost: {uri}")

    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")

    logger.info(f"Connecting to Neo4j at {uri}")
    logger.info(f"User: {user}")

    migrator = SchemaMigrator(uri, user, password)

    try:
        await migrator.run_full_migration()
    finally:
        await migrator.close()


if __name__ == "__main__":
    asyncio.run(main())

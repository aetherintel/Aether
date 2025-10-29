# ============================================================================
# workers/classification_worker/neo4j_utils.py
# Neo4j utilities matching aether_lib architecture
# ============================================================================

import logging
from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)


async def store_classifications_in_neo4j(
    driver,
    message_id: str,
    classifications: list,
    owner_id: str = None
):
    """
    Store classification results in Neo4j using aether_lib architecture
    
    Args:
        driver: Neo4j AsyncGraphDatabase driver
        message_id: Message ID (format: channel_id-message_id)
        classifications: List of classification results
        owner_id: Owner ID for multi-tenancy (optional)
    
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(f"💾 [STORE] Storing {len(classifications)} classifications for {message_id}")
    
    try:
        async with driver.session() as session:
            for cls in classifications:
                await session.run(
                    """
                    // Find the Message node (with or without owner_id filter)
                    MATCH (m:Message {mid: $message_id})
                    WHERE $owner_id IS NULL OR m.owner_id = $owner_id
                    
                    // Create or update Classification node
                    MERGE (c:Classification {label_id: $label_id})
                    ON CREATE SET 
                        c.name = $label,
                        c.label_id = $label_id,
                        c.description = $description,
                        c.created_at = datetime()
                    
                    // Create or update relationship
                    MERGE (m)-[r:HAS_CLASSIFICATION]->(c)
                    ON CREATE SET
                        r.confidence = $confidence,
                        r.method = $method,
                        r.detected_at = datetime()
                    ON MATCH SET
                        r.confidence = CASE 
                            WHEN $confidence > r.confidence 
                            THEN $confidence 
                            ELSE r.confidence 
                        END,
                        r.method = $method,
                        r.updated_at = datetime()
                    
                    // Update Message node to track classification status
                    SET m.classification_status = 'completed',
                        m.classified_at = datetime()
                    
                    RETURN m.mid as mid
                    """,
                    message_id=message_id,
                    owner_id=owner_id,
                    label_id=cls['label_id'],
                    label=cls['label'],
                    description=cls.get('description', ''),
                    confidence=cls['confidence'],
                    method=cls.get('method', 'zero-shot')
                )
        
        logger.info(f"✅ [STORE] Successfully stored {len(classifications)} classifications")
        return True
        
    except Exception as e:
        logger.error(f"❌ [STORE] Failed to store classifications: {e}")
        logger.exception("Full traceback:")
        return False


async def get_messages_pending_classification(
    driver,
    owner_id: str = None,
    case_id: str = None,
    limit: int = 1000
):
    """
    Get messages that need classification
    
    Args:
        driver: Neo4j AsyncGraphDatabase driver
        owner_id: Owner ID for filtering (optional)
        case_id: Case ID for filtering (optional)
        limit: Maximum number of messages to return
    
    Returns:
        list: Messages ready for classification
    """
    logger.info(f"🔍 [QUERY] Finding messages pending classification")
    logger.info(f"   Owner: {owner_id or 'ALL'}")
    logger.info(f"   Case: {case_id or 'ALL'}")
    logger.info(f"   Limit: {limit}")
    
    try:
        async with driver.session() as session:
            # Build query based on filters
            if case_id:
                # Filter by case
                query = """
                MATCH (c:Case {id: $case_id})-[:CONTAINS]->(ch:Channel)
                      -[:HAS_MESSAGE]->(m:Message)
                WHERE NOT (m)-[:HAS_CLASSIFICATION]->()
                  AND (m.classification_status IS NULL OR m.classification_status = 'none')
                  AND (
                    (m.translated_text IS NOT NULL AND m.translated_text <> '')
                    OR (m.original_text IS NOT NULL AND m.original_text <> '')
                  )
                  AND ($owner_id IS NULL OR m.owner_id = $owner_id)
                RETURN m.mid as message_id,
                       COALESCE(m.translated_text, m.original_text) as text,
                       m.owner_id as owner_id,
                       m.original_language as language
                ORDER BY m.date DESC
                LIMIT $limit
                """
                params = {
                    "case_id": case_id,
                    "owner_id": owner_id,
                    "limit": limit
                }
            else:
                # All messages
                query = """
                MATCH (m:Message)
                WHERE NOT (m)-[:HAS_CLASSIFICATION]->()
                  AND (m.classification_status IS NULL OR m.classification_status = 'none')
                  AND (
                    (m.translated_text IS NOT NULL AND m.translated_text <> '')
                    OR (m.original_text IS NOT NULL AND m.original_text <> '')
                  )
                  AND ($owner_id IS NULL OR m.owner_id = $owner_id)
                RETURN m.mid as message_id,
                       COALESCE(m.translated_text, m.original_text) as text,
                       m.owner_id as owner_id,
                       m.original_language as language
                ORDER BY m.date DESC
                LIMIT $limit
                """
                params = {
                    "owner_id": owner_id,
                    "limit": limit
                }
            
            result = await session.run(query, **params)
            messages = []
            
            async for record in result:
                messages.append({
                    "message_id": record["message_id"],
                    "text": record["text"],
                    "owner_id": record["owner_id"],
                    "language": record["language"]
                })
            
            logger.info(f"✅ [QUERY] Found {len(messages)} messages pending classification")
            return messages
            
    except Exception as e:
        logger.error(f"❌ [QUERY] Failed to query messages: {e}")
        logger.exception("Full traceback:")
        return []


async def mark_classification_failed(
    driver,
    message_id: str,
    error: str,
    owner_id: str = None
):
    """
    Mark classification as failed for a message
    
    Args:
        driver: Neo4j AsyncGraphDatabase driver
        message_id: Message ID
        error: Error message
        owner_id: Owner ID for filtering (optional)
    """
    try:
        async with driver.session() as session:
            await session.run(
                """
                MATCH (m:Message {mid: $message_id})
                WHERE $owner_id IS NULL OR m.owner_id = $owner_id
                SET m.classification_status = 'failed',
                    m.classification_error = $error,
                    m.classification_failed_at = datetime()
                RETURN m.mid as mid
                """,
                message_id=message_id,
                error=error,
                owner_id=owner_id
            )
        logger.info(f"❌ [STATUS] Marked message {message_id} classification as failed")
    except Exception as e:
        logger.error(f"❌ [STATUS] Failed to mark classification failed: {e}")


async def get_classification_statistics(
    driver,
    owner_id: str = None,
    case_id: str = None
):
    """
    Get classification statistics
    
    Args:
        driver: Neo4j AsyncGraphDatabase driver
        owner_id: Owner ID for filtering (optional)
        case_id: Case ID for filtering (optional)
    
    Returns:
        dict: Statistics by label
    """
    try:
        async with driver.session() as session:
            if case_id:
                query = """
                MATCH (c:Case {id: $case_id})-[:CONTAINS]->(ch:Channel)
                      -[:HAS_MESSAGE]->(m:Message)
                      -[r:HAS_CLASSIFICATION]->(cls:Classification)
                WHERE $owner_id IS NULL OR m.owner_id = $owner_id
                RETURN cls.label_id as label_id,
                       cls.name as label,
                       COUNT(DISTINCT m) as count,
                       AVG(r.confidence) as avg_confidence
                ORDER BY count DESC
                """
                params = {"case_id": case_id, "owner_id": owner_id}
            else:
                query = """
                MATCH (m:Message)-[r:HAS_CLASSIFICATION]->(cls:Classification)
                WHERE $owner_id IS NULL OR m.owner_id = $owner_id
                RETURN cls.label_id as label_id,
                       cls.name as label,
                       COUNT(DISTINCT m) as count,
                       AVG(r.confidence) as avg_confidence
                ORDER BY count DESC
                """
                params = {"owner_id": owner_id}
            
            result = await session.run(query, **params)
            stats = []
            
            async for record in result:
                stats.append({
                    "label_id": record["label_id"],
                    "label": record["label"],
                    "count": record["count"],
                    "avg_confidence": record["avg_confidence"]
                })
            
            return stats
            
    except Exception as e:
        logger.error(f"❌ [STATS] Failed to get statistics: {e}")
        return []
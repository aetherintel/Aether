# lib/workers/base_worker.py
"""
Base worker class for all processing workers
"""
import os
import time
import logging
import asyncio
from typing import Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """Abstract base class for all processing workers"""
    
    def __init__(self, worker_name: str):
        self.worker_name = worker_name
        self.owner_id = os.getenv("OWNER_ID", "unknown")
    
    @abstractmethod
    def process(self, **kwargs) -> Dict[str, Any]:
        """Main processing logic - must be implemented by each worker"""
        pass
    
    @abstractmethod
    async def update_neo4j(self, message_id: str, results: Dict[str, Any]) -> bool:
        """Update Neo4j with processing results"""
        pass
    
    def execute(self, message_id: str, **kwargs) -> Dict[str, Any]:
        """
        Execute the full processing pipeline
        This is the main entry point called by RQ
        """
        start_time = time.time()
        logger.info(f"[{self.worker_name}] Starting job for message {message_id}")
        
        try:
            # Step 1: Process
            results = self.process(**kwargs)
            
            if results.get('status') == 'error':
                raise Exception(results.get('error', 'Unknown error'))
            
            # Step 2: Update Neo4j
            success = asyncio.run(self.update_neo4j(message_id, results))
            
            if not success:
                raise Exception("Failed to update Neo4j")
            
            # Step 3: Return results
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[{self.worker_name}] ✓ Completed in {elapsed_ms}ms")
            
            return {
                'status': 'completed',
                'worker': self.worker_name,
                'message_id': message_id,
                'elapsed_ms': elapsed_ms,
                'results': results
            }
            
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"[{self.worker_name}] ✗ Failed: {e}", exc_info=True)
            
            # Try to mark as failed in Neo4j
            try:
                asyncio.run(self._mark_failed(message_id, str(e)))
            except Exception as update_error:
                logger.error(f"Failed to mark as failed: {update_error}")
            
            return {
                'status': 'failed',
                'worker': self.worker_name,
                'message_id': message_id,
                'elapsed_ms': elapsed_ms,
                'error': str(e)
            }
    
    async def _mark_failed(self, message_id: str, error: str):
        """Mark processing as failed in Neo4j"""
        from aether_lib.neo4j_client.messages import mark_translation_failed
        await mark_translation_failed(message_id, error)
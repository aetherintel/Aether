import asyncio
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class TaskRegistry:
    _instance = None
    _tasks: Dict[str, asyncio.Task] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskRegistry, cls).__new__(cls)
        return cls._instance

    def register_task(self, request_id: str, task: asyncio.Task):
        """Register a task with a unique request ID."""
        if not request_id:
            return
        if request_id in self._tasks:
            logger.warning(f"Task with ID {request_id} already exists. Overwriting.")
            # Ideally cancel the old one?
            existing = self._tasks[request_id]
            if not existing.done():
                existing.cancel()
        
        self._tasks[request_id] = task
        # Add callback to remove task when done to prevent memory leak
        task.add_done_callback(lambda t: self._cleanup_task(request_id))
        logger.info(f"Task {request_id} registered.")

    def _cleanup_task(self, request_id: str):
        """Remove task from registry after completion."""
        if request_id in self._tasks:
            del self._tasks[request_id]
            logger.debug(f"Task {request_id} cleaned up.")

    async def cancel_task(self, request_id: str) -> bool:
        """Cancel a running task by ID."""
        task = self._tasks.get(request_id)
        if task and not task.done():
            logger.info(f"Cancelling task {request_id}")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"Task {request_id} successfully cancelled.")
            except Exception as e:
                logger.error(f"Error while cancelling task {request_id}: {e}")
            return True
        elif task and task.done():
            logger.info(f"Task {request_id} already completed.")
            return False
        else:
            logger.warning(f"Task {request_id} not found.")
            return False

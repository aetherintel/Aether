import os
import redis
from rq import Queue

def check_queues():
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    
    queues_config = {
        'telegram': 0,
        'translation': 1,
        'image': 2,
        'audio': 3,
        'emotion': 4,
        'classification': 5,
        'geolocation': 6,
    }
    
    print(f"Connecting to Redis at {redis_host}:{redis_port}")
    
    for name, db in queues_config.items():
        print(f"\n--- Checking Queue: {name} (DB {db}) ---")
        try:
            conn = redis.Redis(host=redis_host, port=redis_port, db=db)
            queue_name = f"{name}-jobs"
            q = Queue(queue_name, connection=conn)
            
            count = len(q)
            print(f"Jobs in queue: {count}")
            
            if count > 0:
                print("First 5 jobs:")
                jobs = q.jobs[:5]
                for job in jobs:
                    print(f"  Job ID: {job.id}")
                    print(f"  Status: {job.get_status()}")
                    print(f"  Origin: {job.origin}")
                    print(f"  Func: {job.func_name}")
                    print(f"  Args: {job.args}")
                    print(f"  Kwargs: {job.kwargs}")
                    print(f"  Meta: {job.meta}")
                    print("  -")
            else:
                print("Queue is empty.")
                
            # Check registries
            from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry
            
            started = StartedJobRegistry(queue=q)
            print(f"Started jobs: {len(started)}")
            
            finished = FinishedJobRegistry(queue=q)
            print(f"Finished jobs: {len(finished)}")
            
            failed = FailedJobRegistry(queue=q)
            print(f"Failed jobs: {len(failed)}")
            if len(failed) > 0:
                print("  First 5 failed job IDs:", failed.get_job_ids()[:5])

        except Exception as e:
            print(f"Error checking queue {name}: {e}")

if __name__ == "__main__":
    check_queues()

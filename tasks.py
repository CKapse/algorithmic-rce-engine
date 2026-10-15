import os
import json
import redis
from celery import Celery
from worker import execute_cpp_submission

redis_url = os.getenv('REDIS_URL', 'redis://redis-broker:6379/0')
app = Celery('rce_tasks', broker=redis_url, backend=redis_url)

# Initialize Redis client for publishing live status updates
redis_client = redis.from_url(redis_url)

@app.task(bind=True, name='tasks.evaluate_code')
def evaluate_code(self, source_code: str, input_data: str = "") -> dict:
    job_id = self.request.id
    
    def publish_status(status_str, output=""):
        payload = {"status": status_str, "output": output}
        redis_client.publish(job_id, json.dumps(payload))

    # Broadcast initial processing state
    publish_status("Compiling Docker Container...")
    
    try:
        # Run the heavy sandboxing logic
        result = execute_cpp_submission(source_code, input_data)
        
        # Broadcast final success payload
        publish_status("Finished", result.get('output', ''))
        return result
        
    except Exception as e:
        # Broadcast failure payload
        publish_status("FAILURE", str(e))
        raise e
# test_queue.py
from tasks import evaluate_code
import time

cpp_code = """
#include <iostream>
int main() {
    std::cout << "Hello from the Redis Queue!" << std::endl;
    return 0;
}
"""

print("Sending job to queue...")
# .delay() is how Celery sends the function arguments to Redis instead of running it immediately
job = evaluate_code.delay(cpp_code, "") 

print(f"Job ID: {job.id}")
print("Waiting for worker to process...")

# Wait for the Celery worker to finish executing the Docker sandbox and return the result
while not job.ready():
    time.sleep(0.5)

print("Result from worker:")
print(job.result)
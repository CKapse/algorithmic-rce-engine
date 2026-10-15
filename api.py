import os
import json
import pymysql
import redis
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from tasks import evaluate_code, app as celery_app

app = Flask(__name__)
CORS(app)

# Database Config
DB_HOST = os.getenv('DB_HOST', 'mysql-service')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'admin123')
DB_NAME = os.getenv('DB_NAME', 'judge_db')

# Redis Config for Pub/Sub Streaming
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis-broker:6379/0')
redis_client = redis.from_url(REDIS_URL)

def get_db_connection():
    return pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

def init_db():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS submissions (
                    job_id VARCHAR(255) PRIMARY KEY,
                    source_code TEXT,
                    status VARCHAR(50),
                    output TEXT
                )
            ''')
        conn.commit()
        conn.close()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Waiting for database connection... {e}")

@app.route('/submit', methods=['POST'])
def submit_code():
    data = request.get_json()
    if not data or 'source_code' not in data:
        return jsonify({"error": "No source_code provided"}), 400
    
    source = data['source_code']
    std_input = data.get('input_data', "")

    # 1. Send task to Celery
    job = evaluate_code.delay(source, std_input)

    # 2. Log initial state to MySQL
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO submissions (job_id, source_code, status, output) VALUES (%s, %s, %s, %s)",
                (job.id, source, "Queued", "")
            )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database error on submit: {e}")

    return jsonify({"job_id": job.id, "status": "Queued"}), 202

@app.route('/stream/<job_id>', methods=['GET'])
def stream_status(job_id):
    """
    Server-Sent Events (SSE) endpoint.
    Checks MySQL first to prevent race conditions, then subscribes to a Redis channel.
    """
    def event_stream():
        # 1. Race Condition Fix: Check if job is ALREADY finished before subscribing
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT status, output FROM submissions WHERE job_id = %s", (job_id,))
                row = cursor.fetchone()
                if row and row['status'] in ['Finished', 'Accepted', 'SUCCESS', 'FAILURE']:
                    yield f"data: {json.dumps({'status': row['status'], 'output': row['output']})}\n\n"
                    conn.close()
                    return # Exit generator immediately
            conn.close()
        except Exception as e:
            print(f"Database check error: {e}")

        # 2. If not finished, open the live Redis stream
        pubsub = redis_client.pubsub()
        pubsub.subscribe(job_id)
        
        for message in pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'])
                # Yield the SSE formatted string
                yield f"data: {json.dumps(data)}\n\n"
                
                # Close the stream if the job has finished
                if data.get('status') in ['Finished', 'Accepted', 'SUCCESS', 'FAILURE']:
                    
                    # Update MySQL with final result before closing
                    try:
                        conn = get_db_connection()
                        with conn.cursor() as cursor:
                            cursor.execute(
                                "UPDATE submissions SET status = %s, output = %s WHERE job_id = %s",
                                (data.get('status'), data.get('output', ''), job_id)
                            )
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        print(f"Database error on final save: {e}")
                    
                    # Unsubscribe and break the generator loop
                    pubsub.unsubscribe()
                    break

    return Response(event_stream(), mimetype='text/event-stream')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
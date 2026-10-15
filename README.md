# ⚡ Distributed Remote Code Execution (RCE) Engine

A highly scalable, distributed execution engine designed to safely compile and run untrusted C++ code in isolated environments. Built with a microservices architecture, this platform features real-time execution streaming and dynamic Kubernetes auto-scaling to handle high-traffic workloads.

## 🚀 Key Features
* **Sandboxed Execution:** Compiles and runs user-submitted C++ code inside ephemeral, completely isolated Docker-in-Docker (DinD) containers.
* **Real-Time Streaming:** Utilizes Redis Pub/Sub and Server-Sent Events (SSE) to stream execution status (Compiling, Running, Output) directly to the browser with zero polling delay.
* **Horizontal Auto-Scaling:** Kubernetes Horizontal Pod Autoscaler (HPA) dynamically provisions new Celery workers based on live CPU telemetry to handle traffic spikes.
* **Professional Editor:** Frontend integrated with the Monaco Editor (VS Code engine) for native syntax highlighting and formatting.
* **Asynchronous Queuing:** Robust task brokering via Celery and Redis ensures no code submissions are lost during heavy load.

## 🛠️ Tech Stack
* **Frontend:** Vanilla JS, HTML/CSS, Monaco Editor API, Server-Sent Events (SSE)
* **Backend API:** Python, Flask, Flask-CORS
* **Task Queue:** Celery, Redis
* **Database:** MySQL
* **Infrastructure:** Docker, Kubernetes (Minikube), Docker-in-Docker (DinD)

## 🏗️ System Architecture

1. **Submission:** The user submits C++ code and `stdin` via the Monaco Editor UI.
2. **API Ingestion:** The Flask API logs the initial state to MySQL and pushes a background task to the Redis message broker.
3. **Task Consumption:** A Celery worker picks up the job and immediately publishes a "Compiling" status to a Redis Pub/Sub channel. 
4. **Execution:** The worker spins up an isolated Docker container, mounts the code, compiles it using `g++`, and captures `stdout` and `stderr`.
5. **Real-Time Delivery:** The Flask API subscribes to the Redis Pub/Sub channel and streams the live output back to the client's browser via an SSE connection.
6. **Auto-Scaling:** If CPU usage across the worker nodes exceeds 50%, Kubernetes HPA automatically spins up additional Celery replicas.

## 💻 Local Deployment

### Prerequisites
* Docker
* Minikube & `kubectl`

### Setup Instructions
1. **Start Minikube and enable the metrics server for auto-scaling:**
   ```bash
   minikube start
   minikube addons enable metrics-server
   ```
2. **Build and load the unified backend image into Minikube:**
   ```bash
   docker build -t rce-backend:latest .
   minikube image load rce-backend:latest
   ```
3. **Deploy the microservices to Kubernetes:**
   ```bash
   kubectl apply -f k8s/
   ```
4. **Expose the Flask API via Minikube tunnel:**
   ```bash
   minikube service flask-api --url
   ```
5. Paste the generated port into the frontend UI and run your code!
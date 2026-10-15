FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Python scripts into the container
COPY . .

# We do not define a CMD here because we will use this exact same image 
# to run the Flask pod AND the Celery worker pod in Kubernetes.
# Combined Dockerfile for AWS App Runner
# Runs both FastAPI backend and Streamlit frontend

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy streamlit requirements and install
COPY streamlit_app/requirements.txt /app/streamlit_app/requirements.txt
RUN pip install --no-cache-dir -r /app/streamlit_app/requirements.txt

# Copy application code
COPY backend/app /app/backend/app
COPY streamlit_app/app.py /app/streamlit_app/app.py

# Supervisor configuration
RUN mkdir -p /etc/supervisor/conf.d
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose ports
EXPOSE 8000 8501

# Set environment variables
ENV PYTHONPATH=/app/backend
ENV BACKEND_URL=http://localhost:8000

# Run with supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

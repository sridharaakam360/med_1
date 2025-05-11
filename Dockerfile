# Use the official Python 3.9 slim image as the base
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV PORT=5000
# Set a fixed SECRET_KEY for production (replace with your own secret in production)
ENV SECRET_KEY="51f52814d7bb5d8d7cb5ec61a9b05f237c6ca5f87cc21cdd"

# Copy requirements file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create database directory with proper permissions
RUN mkdir -p /app/database && chmod 777 /app/database
RUN mkdir -p /app/instance && chmod 777 /app/instance

# Expose the port the app runs on
EXPOSE 5000

# Health check to ensure the app is running
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

# Command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--timeout", "120", "app:app"]
# Use the official Python 3.9 slim image as the base
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if needed, e.g., for SQLite)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Copy requirements file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies directly (no virtualenv, since we're in a container)
RUN pip install --no-cache-dir -r requirements.txt

# Verify gunicorn is installed
RUN pip show gunicorn || { echo "gunicorn not installed"; exit 1; }
RUN which gunicorn || { echo "gunicorn executable not found"; exit 1; }

# Copy the rest of the application code
COPY . .

# Create database directory
RUN mkdir -p /app/database

# Expose the port the app runs on
EXPOSE 5000

# Set environment variables for production
ENV PORT=5000
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# Health check to ensure the app is running
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

# Command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--timeout", "120", "app:app"]
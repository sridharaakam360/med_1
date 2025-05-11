# Stage 1: Build the application
FROM python:3.9-slim AS builder

# Set working directory
WORKDIR /app

# Copy requirements file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies in a virtual environment
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Create the runtime image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Create a non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Copy installed dependencies from the builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Copy the rest of the application code
COPY . .

# Ensure the virtual environment is in the PATH
ENV PATH=/home/appuser/.local/bin:$PATH

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
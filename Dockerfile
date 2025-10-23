FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create directory for database volume
RUN mkdir -p /app/data

# Expose Flask API port
EXPOSE 5000

# Make startup script executable
RUN chmod +x /app/start.sh

# Run the startup script
CMD ["/app/start.sh"]

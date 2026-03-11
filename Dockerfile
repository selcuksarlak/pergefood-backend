FROM python:3.11-slim

# System dependencies for pymssql, Pillow, etc.
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    freetds-dev \
    freetds-bin \
    libssl-dev \
    libffi-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create static directories
RUN mkdir -p static/product_images static/offers uploads/invoices app/ml/models

# Expose port (Railway sets $PORT automatically)
EXPOSE 8000

# Start FastAPI
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

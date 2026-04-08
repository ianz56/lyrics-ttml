FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY import_ttml.py .

# Copy TTML source files for the import script
COPY ENG/ ./ENG/
COPY KOR/ ./KOR/
COPY IND/ ./IND/
COPY MYS/ ./MYS/
COPY SUN/ ./SUN/
COPY ELRC/ ./ELRC/

EXPOSE 8000

# Default command: run the API server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

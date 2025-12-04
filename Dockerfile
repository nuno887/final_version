# 1. Base image
FROM python:3.12-slim

# 2. Environment settings (no .pyc, unbuffered logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 3. Workdir inside the container
WORKDIR /app

# 4. Install system deps (optional, extend if your PDF libs need more)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy your app code
COPY . .

# 7. Expose FastAPI port
EXPOSE 8000

# 8. Start the server
# api:app  -> api.py file with `app = FastAPI()`
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]

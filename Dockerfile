FROM python:3.12-slim

WORKDIR /app

# System deps + Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium chromium-driver curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] duckdb xgboost lightgbm scikit-learn \
    pulp requests beautifulsoup4 pydantic pydantic-settings httpx \
    pandas numpy scipy apscheduler bcrypt "python-jose[cryptography]"

# Frontend build
COPY frontend/package.json frontend/package-lock.json* frontend/
RUN cd frontend && npm ci
COPY frontend/ frontend/
RUN cd frontend && npx vite build

# Backend + configs
COPY backend/ backend/
COPY configs/ configs/

# Create data dir (populated at runtime)
RUN mkdir -p data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

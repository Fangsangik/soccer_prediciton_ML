FROM python:3.12-slim

WORKDIR /app

# System deps for soccerdata/chromedriver
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium chromium-driver curl && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[all]" 2>/dev/null || pip install --no-cache-dir \
    fastapi uvicorn[standard] duckdb xgboost lightgbm scikit-learn \
    pulp requests beautifulsoup4 pydantic pydantic-settings httpx \
    pandas numpy scipy apscheduler soccerdata

# Frontend build
COPY frontend/package.json frontend/package-lock.json* frontend/
RUN cd frontend && npm ci --production=false 2>/dev/null || (cd frontend && npm install)
COPY frontend/ frontend/
RUN cd frontend && npx vite build

# Backend
COPY backend/ backend/
COPY configs/ configs/
COPY data/ data/

# Create data dir
RUN mkdir -p data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

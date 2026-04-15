.PHONY: dev backend frontend build seed test clean

# Run both backend and frontend in development mode
dev: backend frontend

# Start FastAPI backend on port 8000
backend:
	cd /Users/hwangsang-ik/claude-workspace-dashboard-template/football-analytics && \
	python -m uvicorn backend.main:app --port 8000 --reload

# Start Vite dev server on port 5173
frontend:
	cd /Users/hwangsang-ik/claude-workspace-dashboard-template/football-analytics/frontend && \
	npx vite --port 5173

# Build frontend for production
build:
	cd /Users/hwangsang-ik/claude-workspace-dashboard-template/football-analytics/frontend && \
	npx vite build

# Seed database with mock data
seed:
	cd /Users/hwangsang-ik/claude-workspace-dashboard-template/football-analytics && \
	python -c "from backend.db import init_db, get_db; init_db(); from backend.collectors.mock_data import seed_mock_data; seed_mock_data(get_db()); print('Done')"

# Run tests
test:
	cd /Users/hwangsang-ik/claude-workspace-dashboard-template/football-analytics && \
	python -m pytest tests/ -v

# Clean generated files
clean:
	rm -f data/football.duckdb
	rm -rf frontend/dist

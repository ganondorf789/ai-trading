# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Trading Platform for analyzing traders on the Hyperliquid decentralized exchange, executing copy trading strategies, and managing positions with AI assistance. Full-stack application with a React/TypeScript frontend and Python Flask backend.

## Architecture

**Frontend (`web/`):** React 18 + TypeScript, built with Vite 6, styled with Tailwind CSS 4 and HeroUI v2 component library. Uses React Router v6 for routing, Axios for API calls with JWT auth interceptors, and Recharts for data visualization.

**Backend (`services/`):** Flask 3.0 with modular blueprint-based routing. Swagger docs at `/docs` via Flasgger. WebSocket support via Flask-SocketIO for real-time position updates.

**Database (`database/`):** PostgreSQL 16 (port 5433) with psycopg2 connection pooling. Raw SQL with `RealDictCursor`. Schema defined in individual module files (e.g., `database/traders.py`, `database/copy_trading.py`). No ORM.

**Cache:** Redis 7 (port 6380) for caching and pub/sub (position change events).

**Configuration (`config/settings.py`):** Pydantic BaseSettings classes with env var prefixes (`POSTGRES_`, `REDIS_`, `HYPERLIQUID_`, etc.).

**Trader Screener (`screener/`):** Standalone module for analyzing and scoring traders from Hyperliquid leaderboard data.

**Trading Engine (`trading/`):** Copy trading bot with its own Flask server, gRPC client, and position management logic. Core logic in `trading/position_copy_trading.py`.

**gRPC (`protos/`):** Inter-service communication between API server and trading service (port 50051).

### Key Entry Points

- `api_server.py` — Flask API server (default port 5000)
- `trading_server.py` — Trading service
- `grpc_server.py` — gRPC server
- `monitor_s_traders_positions.py` — Position monitoring script (use `--redis` flag for WebSocket notifications)

### Frontend API Client

All API calls are defined in `web/src/services/api.ts` (~1150 lines). Organized into named API objects: `traderApi`, `copyTradingApi`, `traderPositionsApi`, `positionTrackingApi`, `riskControlApi`, `authApi`, `userManagementApi`, `secretKeyApi`, `appVersionApi`, `announcementApi`, `addressTrackingApi`, `whaleAnchorApi`. Types are in `web/src/types/`.

### Frontend Page Structure

Page components live in `web/src/pages/{page-name}/` with page-specific sub-components in a `components/` subdirectory. Shared components are in `web/src/components/`.

## Commands

### Frontend (run from `web/`)

```bash
pnpm install          # Install dependencies
pnpm dev              # Dev server with HMR
pnpm build            # TypeScript check + Vite production build
pnpm lint             # ESLint with auto-fix
pnpm preview          # Preview production build
```

### Backend

```bash
pip install -r requirements.txt           # Install Python dependencies
python api_server.py                      # Start API server (port 5000)
python api_server.py --port 8080          # Custom port
python api_server.py --no-websocket       # Disable WebSocket
```

### Infrastructure

```bash
docker compose up -d        # Start PostgreSQL (5433) and Redis (6380)
docker compose down          # Stop services
```

### Tests

```bash
pytest                       # Run all Python tests
pytest path/to/test.py       # Run single test file
pytest -k "test_name"        # Run tests matching pattern
```

## Key Conventions

- The codebase uses Chinese comments extensively throughout the Python backend
- Frontend path alias: `@/*` maps to `web/src/*` (configured in tsconfig)
- Auth tokens stored in localStorage; Axios interceptors handle token refresh and 401 redirects automatically
- Database classes inherit from `DatabaseBase` (`database/base.py`) which provides connection pooling and cursor context managers
- Backend routes use Flask blueprints registered in `services/routes/__init__.py`
- Environment variables are loaded via `.env` file; see `config/settings.py` for all available settings and their defaults

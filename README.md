# VGrand Restaurant Order Conflict Resolution Engine

A real-time order processing system for VGrand Restaurant that handles concurrent orders from POS terminals, mobile delivery apps, and web reservations. The system resolves conflicts deterministically using event sourcing with a single reducer function, maintains versioned auditable state, and supports replay of events to reconstruct any historical state.

## Architecture

**Core Design: Event Sourcing + Deterministic Reducer**

- Every incoming event is stored immutably in the `Event` table
- Order state is computed by replaying all events for an order through a single reducer function
- The reducer sorts events by `(timestamp, source_priority, event_id)` — ensuring determinism
- This one function handles: live processing, late-event handling, and the replay endpoint
- `OrderState` is an append-only projection (never mutated — each resolution creates a new version)
- `AuditLog` captures the full decision trace for every processed event

```
POST /api/events → validate → dedup check → save Event (immutable)
                                         → reducer(events_sorted) → new OrderState version
                                         → AuditLog entry
                                         → response (state + decision)
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (optional — SQLite is used by default for local dev)

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt

# Optional: Set DATABASE_URL for PostgreSQL/Supabase
# export DATABASE_URL="postgresql://user:pass@host:port/dbname"
# On Windows (PowerShell): $env:DATABASE_URL="postgresql://user:pass@host:port/dbname"
# Or create a .env file (see .env.example)

python manage.py migrate
python manage.py runserver
```

The API will be available at `http://localhost:8000/api/`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The dashboard will be available at `http://localhost:5173`

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/events` | Submit an order event |
| GET | `/api/orders` | List all orders with current state |
| GET | `/api/orders/{id}` | Get current order state |
| GET | `/api/orders/{id}/history` | Get all versioned states |
| GET | `/api/orders/{id}/audit` | Get audit trail |
| GET | `/api/orders/{id}/replay` | Replay events to reconstruct state |
| GET | `/api/orders/{id}/replay?up_to=ISO8601` | Replay up to a point in time |
| GET | `/api/orders/{id}/state?version=N` | Get state at specific version |
| GET | `/api/orders/{id}/state?timestamp=ISO` | Get state as of timestamp |
| GET | `/api/locations` | List all restaurant locations |
| GET | `/api/inventory/{location_id}` | Get inventory for a location |
| GET | `/api/anomalies` | List anomaly alerts |
| GET | `/api/stats` | System statistics (events, orders, audit, rejected) |
| POST | `/api/notify/driver` | Dummy driver notification |
| GET | `/api/health` | Health check |

## Event Payload Format

```json
{
  "event_id": "evt-001",
  "source": "pos",
  "order_id": "ORD-001",
  "timestamp": "2026-08-15T10:00:00Z",
  "items": [{"name": "Burger", "quantity": 2}],
  "status": "pending"
}
```

- `source`: `pos`, `mobile`, or `web`
- `status`: `pending`, `preparing`, `ready`, `delivered`, or `cancelled`
- `items`: optional (empty = no item change). Use `quantity: 0` to remove an item.

## Conflict Resolution Rules

| Case | Rule |
|------|------|
| Duplicate `event_id` | Ignored — returns existing state (idempotent) |
| Late event | Inserted and all events replayed in canonical order |
| Conflicting item reservations | Resolved by timestamp, then source priority (POS > mobile > web) |
| Conflicting status updates | Latest timestamp wins; ties broken by source priority |
| Missing/empty items | No item change, only status update |
| Partial item update | Merge by name: qty > 0 adds/overwrites, qty = 0 removes |
| Invalid status transition | Rejected (e.g., delivered → preparing); logged in audit; items NOT merged |

**Source priority**: `pos (0) > mobile (1) > web (2)`

**Valid transitions**: `pending → preparing → ready → delivered`, any → `cancelled` (terminal)

## Sample Data

Fixture files are in `backend/fixtures/`:

| File | Edge Case |
|------|-----------|
| `01_duplicate_events.json` | Same event_id submitted twice |
| `02_late_out_of_order.json` | Event with earlier timestamp arrives late |
| `03_conflicting_reservations.json` | Same order, same timestamp, different sources, different quantities — priority tiebreak |
| `04_conflicting_statuses.json` | Two valid status updates at same timestamp — POS priority determines order |
| `05_partial_updates.json` | Item add, quantity change, item removal |
| `06_out_of_order_transitions.json` | Invalid backward status transition |
| `07_anomaly_pattern.json` | Repeated late events from same source |

### Loading Fixtures

```bash
cd backend

# Load a single fixture
python manage.py load_fixture fixtures/01_duplicate_events.json

# Load with inventory seeding (creates default Location + MenuItems)
python manage.py load_fixture fixtures/01_duplicate_events.json --seed-inventory

# Load all fixtures
for f in fixtures/*.json; do python manage.py load_fixture "$f"; done
```

Alternatively, POST each event in a fixture array to `/api/events`.

## Running Tests

```bash
cd backend
python manage.py test
```

Tests cover (30 tests):
- Duplicate event handling (idempotency)
- Late event replay (state recomputation)
- Conflicting reservation resolution (within-order, priority tiebreak)
- Conflicting status resolution (same timestamp, priority tiebreak)
- Invalid transition rejection
- Replay matching live state (determinism)
- Replay with `up_to` timestamp filter
- Audit trail completeness and explanation accuracy
- Inventory check and reservation release
- Event validation (malformed events, quantity boundaries)
- 404 handling for nonexistent orders
- Stats endpoint
- IntegrityError race condition handling
- Processing time measurement in response

## Testing Replay and Audit

### Replay
```bash
curl http://localhost:8000/api/orders/ORD-002/replay
curl "http://localhost:8000/api/orders/ORD-002/replay?up_to=2026-08-15T10:05:00Z"
```

### Audit Trail
```bash
curl http://localhost:8000/api/orders/ORD-005/audit
```

### Submit an Event
```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{"event_id": "test-1", "source": "pos", "order_id": "ORD-TEST", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 1}], "status": "pending"}'
```

## Frontend Dashboard

The React dashboard provides:
- **Dashboard**: Overview of all orders with status badges and counts
- **Submit Event**: Form to manually submit events with fixture quick-load buttons
- **Order Detail**: Current state + version history table
- **Audit Trail**: Expandable audit entries with rule explanations and state diffs
- **Replay**: Step-by-step replay timeline with optional `up_to` filter
- **Inventory**: Per-location inventory with stock level bars
- **Anomalies**: Alert panel showing detected anomaly patterns

## Tech Stack

- **Backend**: Django 5.x, Django REST Framework, PostgreSQL (or SQLite), gunicorn, WhiteNoise
- **Frontend**: React 18, Vite, Tailwind CSS — uses native `fetch()`, CSS/SVG timeline, emoji status badges
- **Database**: PostgreSQL via `DATABASE_URL` env var (SQLite fallback)
- **Deployment**: Railway (backend via `Procfile`), Vercel (frontend via `VITE_API_BASE`)

### Environment Variables

| Variable | Where | Default | Description |
|----------|-------|---------|-------------|
| `DATABASE_URL` | backend | SQLite | PostgreSQL connection string |
| `SECRET_KEY` | backend | dev key | Django secret key (set in production) |
| `DEBUG` | backend | `false` | Django debug mode |
| `ALLOWED_HOSTS` | backend | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `CORS_ALLOWED_ORIGINS` | backend | `http://localhost:5173` | Comma-separated CORS origins |
| `VITE_API_BASE` | frontend | `http://localhost:8000/api` | Backend API URL for deployed frontend |

## Postman Collection

Import `docs/postman_collection.json` into Postman for pre-configured API requests.

## Demo Script

1. **Fixture 01**: Shows duplicate events being ignored — idempotency in action.
2. **Fixture 02**: Shows a late event arriving after two newer ones — the reducer sorts it into position and recomputes correctly.
3. **Fixture 03**: Shows two sources conflicting on the same order at the same timestamp — priority tiebreak resolves it.
4. **Fixture 04**: Shows two valid status updates at the same timestamp — POS priority determines processing order.
5. **Fixture 05**: Shows partial item updates including removal via quantity zero — merge logic in action.
6. **Fixture 06**: Shows an invalid backward status transition (ready → preparing) being rejected.
7. **Fixture 07**: Shows repeated late events from the same source triggering anomaly detection.

## Concurrency Assumption

Single-process, synchronous — matches the "no distributed systems" constraint. Not designed for concurrent writes to the same order without the `IntegrityError` fallback in the `submit_event` view (which handles race conditions on duplicate `event_id`).

# 🤖 SquadMind Backend
**AI-Powered CFO Platform for Nigerian SMEs**
*Squad Hackathon 3.0 — "Smart Systems: The Intelligent Economy"*

---

## 🏗️ Architecture Overview

```
Frontend (React/Next.js)
    ↓ HTTP / WebSocket
FastAPI Backend (main.py)
    ↓
API Layer (/app/api/v1/)
    ├── auth.py          → JWT auth, registration, login
    ├── dashboard.py     → Revenue Intelligence Dashboard
    ├── transactions.py  → Transaction listing + Squad sync
    ├── fraud.py         → Fraud flags and scanning
    ├── forecasts.py     → Cash flow projections
    └── alerts.py        → WhatsApp/SMS/Email alerts
    ↓
Services Layer (/app/services/)
    ├── squad_service.py    → Squad API integration
    ├── fraud_service.py    → Rule-based fraud detection
    ├── forecast_service.py → Moving average forecasting
    └── alert_service.py    → Multi-channel notifications
    ↓
Workers (/app/workers/)     → Celery background tasks
    ↓
PostgreSQL + Redis
```

---

## 🚀 Quick Start

### 1. Clone and setup
```bash
git clone <repo>
cd squadmind
cp .env.example .env
# Edit .env with your credentials
```

### 2. Start infrastructure
```bash
docker compose up -d postgres redis
```

### 3. Install dependencies
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run database migrations
```bash
alembic upgrade head
```

### 5. Start the API server
```bash
uvicorn main:app --reload --port 8000
```

### 6. Start Celery worker (separate terminal)
```bash
celery -A app.workers.celery_app worker --loglevel=info
```

### 7. Start Celery Beat scheduler (separate terminal)
```bash
celery -A app.workers.celery_app beat --loglevel=info
```

### Or run everything with Docker
```bash
docker compose up
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register SME account |
| POST | `/api/v1/auth/login` | Login, get JWT tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Get current user profile |
| POST | `/api/v1/auth/squad-credentials` | Save Squad API keys |
| GET | `/api/v1/dashboard/?period=last_30_days` | **Main dashboard payload** |
| GET | `/api/v1/transactions/` | Paginated transactions |
| GET | `/api/v1/transactions/summary` | Analytics summary |
| POST | `/api/v1/transactions/sync` | Trigger Squad API sync |
| GET | `/api/v1/fraud/` | List fraud flags |
| POST | `/api/v1/fraud/scan/{tx_id}` | Manual fraud scan |
| POST | `/api/v1/forecasts/generate` | Generate cash flow forecast |
| GET | `/api/v1/forecasts/latest` | Latest forecast |
| POST | `/api/v1/alerts/test` | Send test alert |
| GET | `/health` | Health check |

**Interactive docs:** http://localhost:8000/docs

---

## 🔑 Auth Flow

```
POST /api/v1/auth/register
→ { access_token, refresh_token, user }

# All subsequent requests:
Authorization: Bearer <access_token>

# Token expired? Use refresh token:
POST /api/v1/auth/refresh
→ { access_token }
```

---

## 🏦 Squad API Integration

1. Register a Squad account at https://dashboard.squadco.com
2. Get your API keys from Settings → API Keys
3. Save them via `POST /api/v1/auth/squad-credentials`
4. Trigger sync via `POST /api/v1/transactions/sync`
5. Background sync runs automatically every 30 minutes

---

## 🕵️ Fraud Detection Rules

| Rule | Score Contribution |
|------|--------------------|
| Large transaction (> ₦500K) | Up to 30 |
| Night-time transaction (11PM–5AM) | 15 |
| Velocity breach (10+ txns/hour) | 35 |
| Round number amount | 10 |
| Potential duplicate | 40 |
| High-value first transaction | 20 |

**Risk Levels:**
- 0–24: Low
- 25–49: Medium
- 50–74: High
- 75–100: Critical

---

## 📊 Forecasting Algorithms

| Algorithm | Description |
|-----------|-------------|
| `moving_average` | 7-day simple moving average extrapolated |
| `weighted_ma` | 14-day weighted (recent days count more) |
| `trend_adjusted` | Linear regression with 30% slope dampening |

---

## 🌍 Environment Variables

See `.env.example` for full list. Key ones:

```env
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://localhost:6379/0
SQUAD_SECRET_KEY=your-squad-key
OPENAI_API_KEY=sk-...
TWILIO_ACCOUNT_SID=...
SENDGRID_API_KEY=SG...
```

---

## 🗄️ Database Schema

```
users          → SME business accounts + Squad credentials
transactions   → Normalised Squad API transactions
fraud_logs     → Fraud detection results + resolutions
forecasts      → Cash flow projection results
alerts         → Notification dispatch records
```

Run migrations: `alembic upgrade head`
Generate new migration: `alembic revision --autogenerate -m "description"`

---

## 🧪 Development

```bash
# Run tests
pytest tests/ -v

# Format code
black app/
isort app/

# Monitor Celery tasks
open http://localhost:5555  # Flower dashboard
```

---

*Built for Squad Hackathon 3.0 🇳🇬*

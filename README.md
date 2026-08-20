# EG PC Builder 🖥️

An AI-powered PC build recommender for the Egyptian market. Scrapes live component prices from [EGPrices.com](https://egprices.com), caches them in Redis, and uses an LLM to generate budget-aware, compatibility-checked builds in seconds.

---

## How It Works

```
EGPrices.com  ──►  Playwright Scraper  ──►  Redis Cache (6h TTL)
                                                    │
                                                    ▼
React Frontend  ◄──  FastAPI /build  ◄──  LLM (Claude / GPT / Gemini / Ollama)
```

1. On startup, the scraper fetches all PC component categories from EGPrices.com
2. Results are cached in Redis with a 6-hour TTL and refreshed on a schedule
3. When a build is requested, live prices are injected into the LLM's context (RAG)
4. The LLM returns a structured JSON build — compatible parts, within budget, with store info

---

## Features

- **Live prices** — scrapes 8 component categories (GPU, CPU, RAM, Motherboard, Storage, PSU, Case, Cooler) across all pages
- **RAG pipeline** — real market data injected into LLM context, no hallucinated prices
- **Multi-provider LLM with automatic fallback** — tries providers in order (e.g. Gemini → GPT → Claude → Ollama) and falls through to the next one on timeout, error, or malformed response, so a single provider outage doesn't fail the request
- **Extensible scraper** — abstract base class makes adding new store scrapers (B.Tech, 2B, etc.) straightforward
- **Redis caching** — fast responses, scraper isn't hammering the site on every request
- **Compatibility checks** — LLM enforced to verify CPU socket, RAM type, and budget adherence
- **Scheduled re-scraping** — APScheduler refreshes the cache automatically every 6 hours
- **Admin endpoints** — inspect cache status, scheduler status, trigger forced re-scrape
- **React frontend** — Vite + React client that talks to the FastAPI backend

---

## Project Structure

```
eg-pc-builder/
├── main.py              # FastAPI app instance, CORS, lifespan (LLM providers + scheduler)
├── config.py             # SCRAPERS list — shared by routes, admin, and the scheduler
├── scheduler.py            # APScheduler setup (6h re-scrape job)
├── models.py                # Pydantic request/response schemas
├── run.py                     # Entry point (Windows event loop fix)
├── requirements.txt
├── .env.example
├── README.md
│
├── routers/
│   ├── build.py               # POST /build
│   ├── prices.py               # GET /prices/{category}
│   └── admin.py                  # /admin/* endpoints
│
├── services/
│   ├── scraper.py               # BaseScraper + EGPricesScraper implementation
│   └── cache.py                  # Redis get/set/warm helpers
│
├── llm/
│   ├── base.py                  # BaseLLM abstract class
│   ├── providers.py               # ClaudeLLM, GPT, GeminiLLM, OllamaLLM + get_llm() factory
│   ├── prompt.py                    # Price block builder, system prompt, response parsing
│   └── fallback.py                    # generate_build_with_fallback() — the provider chain
│
└── frontend/
    ├── src/                      # React components, pages, API client
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── .env.example
```

---

## Prerequisites

- Python 3.11+
- Node.js 18+ and npm (for the frontend)
- Redis — via **WSL2** on Windows (see setup below), or a native/Docker install on macOS/Linux
- An Anthropic, OpenAI, or Gemini API key — or [Ollama](https://ollama.com) for local models

---

## Setup — Backend

### 1. Clone and install dependencies

```bash
git clone https://github.com/yourusername/eg-pc-builder.git
cd eg-pc-builder

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium     # installs the headless browser
```

### 2. Start Redis

**Windows (via WSL2):**

```bash
# Inside your WSL2 distro (one-time install)
sudo apt update && sudo apt install redis-server

# Start it (each session, or enable it to run on boot)
sudo service redis-server start

# Verify — run from WSL or from Windows if the port is forwarded
redis-cli ping   # → PONG
```

Redis listens on `localhost:6379` inside WSL2, which is reachable from Windows as `localhost:6379` too (WSL2 forwards ports to the Windows host automatically), so `REDIS_URL=redis://localhost:6379/0` works unchanged from either side.

**macOS / Linux (Docker alternative):**

```bash
docker run -d --name redis-eg -p 6379:6379 redis:7-alpine
docker exec redis-eg redis-cli ping   # → PONG
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your keys:

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx   # required if using Claude
OPENAI_API_KEY=sk-xxxxxxxx          # required if using GPT
GEMINI_API_KEY=xxxxxxxx             # required if using Gemini

LLM_PROVIDER=claude                 # claude | gpt | gemini | ollama
REDIS_URL=redis://localhost:6379/0
```

> **Note:** `LLM_PROVIDER` controls the single-provider path (`get_llm()`). The `/build` route itself uses the fallback chain configured in `main.py`'s `lifespan()` (`app.state.llm_providers`), which currently tries providers in a fixed order regardless of this variable — update the provider list in `main.py` directly to change that order.

### 4. Run the backend

```bash
# Windows
python run.py                          # wraps uvicorn with reload=True, loop="none" — see note below

# Windows, equivalent without run.py
uvicorn main:app --reload --loop=none

# macOS / Linux
uvicorn main:app --reload
```

> **Why `--loop=none` on Windows:** by default, uvicorn uses `ProactorEventLoop` on Windows in single-process mode, but swaps to `SelectorEventLoop` as soon as `--reload` (or multiple workers) is used. `SelectorEventLoop` can't spawn subprocesses on Windows, which breaks Playwright (`NotImplementedError`) — including during the cache-warming step in `lifespan` on startup. Setting `loop="none"` tells uvicorn to skip its own event-loop setup entirely, so the Windows default (Proactor) is left alone even with `--reload` on. This isn't needed on macOS/Linux, and won't be needed at all once this is running in Docker — Linux containers don't have this Proactor/Selector split in the first place.

The server starts at `http://localhost:8000`. On first startup it scrapes all categories and warms the cache — this takes a few minutes.

---

## Setup — Frontend

The frontend is a Vite + React app in `frontend/`, separate from the Python backend.

### 1. Install dependencies

```bash
cd frontend
npm install
```

### 2. Configure environment

```bash
cp .env.example .env
```

Point it at your running backend:

```bash
# frontend/.env
VITE_API_BASE_URL=http://localhost:8000
```

### 3. Run the dev server

```bash
npm run dev
```

The frontend starts at `http://localhost:5173` (Vite's default) and proxies requests to the backend URL configured above. Make sure the backend (`/build` etc.) is already running, or builds will fail with a connection error.

### 4. Build for production

```bash
npm run build      # outputs static files to frontend/dist
npm run preview     # serve the production build locally to sanity-check it
```

> **CORS:** the backend currently allows all origins (`allow_origins=["*"]` in `main.py`) so the dev server works out of the box. Tighten this to your actual frontend URL before deploying either side.

### Running both together

Two terminals, from the repo root:

```bash
# Terminal 1 — backend
python run.py

# Terminal 2 — frontend
cd frontend && npm run dev
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness check |
| `POST` | `/build` | Generate a PC build (tries providers in order, falls through on failure) |
| `GET` | `/prices/{category}` | Get cached prices for a category |
| `GET` | `/admin/cache-status` | TTL and product count per cache key |
| `GET` | `/admin/scheduler-status` | Scheduler running state and next scheduled re-scrape |
| `POST` | `/admin/scrape` | Force a full re-scrape |
| `DELETE` | `/admin/clear-cache` | Clear all cached prices, or one category via `?category=` |

Interactive docs available at **`http://localhost:8000/docs`** (Swagger UI).

### POST /build — example

```bash
curl -X POST http://localhost:8000/build \
  -H "Content-Type: application/json" \
  -d '{
    "budget": 30000,
    "use_case": "gaming-1080p",
    "priority": "value",
    "notes": "Prefer AMD, already have a case"
  }'
```

```json
{
  "summary": "A solid 1080p gaming build centered around the RX 7600...",
  "feasibility": "feasible",
  "feasibility_note": "Budget allows a balanced build with room for a quality PSU.",
  "total_estimated": 28750,
  "parts": [
    {
      "category": "CPU",
      "name": "AMD Ryzen 5 5600X",
      "price_egp": 11500,
      "store": "B.Tech",
      "notes": "Best value AM4 CPU. Pairs perfectly with any B450/B550 board.",
      "egprices_search": "Ryzen 5 5600X"
    }
  ],
  "alternatives": [...],
  "tips": [...],
  "upgrade_path": "GPU first — moving to an RX 7700 XT would noticeably improve frame rates at 1080p."
}
```

Valid `use_case` values: `gaming-1080p`, `gaming-1440p`, `content-creation`, `workstation`, `streaming`, `office`

Valid `priority` values: `value`, `performance`, `future-proof`, `quiet`

---

## Switching LLM Providers

The single-provider path (`get_llm()` in `llm/providers.py`) reads `LLM_PROVIDER` from `.env` — no code changes needed for that path:

```bash
LLM_PROVIDER=claude    # Anthropic Claude
LLM_PROVIDER=gpt       # OpenAI GPT-4o
LLM_PROVIDER=gemini    # Google Gemini (default in the fallback chain)
LLM_PROVIDER=ollama    # Local model via Ollama (free, no API key)
```

The `/build` route uses `generate_build_with_fallback()` instead, with a fixed provider list set in `main.py`'s `lifespan()`. To change the fallback order or add/remove a provider, edit that list directly:

```python
# main.py
app.state.llm_providers = [
    GeminiLLM(),
    GPT(),
    # ClaudeLLM(),
    # OllamaLLM(model="qwen2.5:3b-instruct"),
]
```

### Using a specific model

```python
# Override the default model for any provider by passing it in the constructor
GeminiLLM(model="gemini-1.5-flash")
OllamaLLM(model="mistral")   # any model you've pulled with ollama pull
```

### Running locally with Ollama

```bash
# Install Ollama from https://ollama.com then:
ollama pull llama3       # or mistral, deepseek-r1, etc.
ollama serve             # starts on http://localhost:11434

# Set in .env:
LLM_PROVIDER=ollama
```

> **Note:** Local models work but produce lower-quality compatibility reasoning than frontier models. Recommended for development, or as a last-resort fallback if cloud providers are unavailable.

---

## Supported Component Categories

| Key | Category |
|-----|----------|
| `gpu` | Graphics Cards |
| `processor` | CPUs |
| `motherboard` | Motherboards |
| `memory` | RAM |
| `storage` | SSDs & HDDs |
| `psu` | Power Supplies |
| `case` | PC Cases |
| `cooler` | CPU Coolers & Fans |

---

## Adding a New Store Scraper

Subclass `BaseScraper` in `services/scraper.py` and implement three methods:

```python
class BTechScraper(BaseScraper):
    SOURCE_NAME = "B.Tech"
    CATEGORIES = {
        "gpu": "https://btech.com/en/gaming/components/graphic-cards.html",
        # ...
    }

    def _card_selector(self) -> str:
        return ".product-item-info"

    def _next_btn_selector(self) -> str:
        return "a.action.next"

    def _parse_cards(self, html: str) -> list[dict]:
        # parse and return list of {name, price_egp, store, source}
        ...
```

Then add it to `SCRAPERS` in `config.py`:

```python
# config.py
SCRAPERS = [
    EGPricesScraper(),
    BTechScraper(),   # ← add here
]
```

Results from all scrapers are automatically merged and deduplicated.

---

## Environment Variables

### Backend (`.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | If using Claude | — | Anthropic API key |
| `OPENAI_API_KEY` | If using GPT | — | OpenAI API key |
| `GEMINI_API_KEY` | If using Gemini | — | Google API key |
| `LLM_PROVIDER` | No | `claude` | Provider for the single-provider `get_llm()` path |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection URL |

### Frontend (`frontend/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_BASE_URL` | No | `http://localhost:8000` | Base URL the frontend calls for `/build`, `/prices`, etc. |

---

## License

MIT
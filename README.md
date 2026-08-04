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
- **Multi-provider LLM** — swap between Claude, GPT, Gemini, or a local Ollama model via a single env var
- **Extensible scraper** — abstract base class makes adding new store scrapers (B.Tech, 2B, etc.) straightforward
- **Redis caching** — fast responses, scraper isn't hammering the site on every request
- **Compatibility checks** — LLM enforced to verify CPU socket, RAM type, and budget adherence
- **Admin endpoints** — inspect cache status, trigger forced re-scrape

---

## Project Structure

```
eg-pc-builder/
├── main.py           # FastAPI app, routes, lifespan
├── scraper.py        # BaseScraper + EGPricesScraper implementation
├── cache.py          # Redis get/set/warm helpers
├── builder.py        # BaseLLM + provider implementations + factory
├── models.py         # Pydantic request/response schemas
├── run.py            # Entry point (Windows event loop fix)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Prerequisites

- Python 3.11+
- Docker (for Redis) — or a local Redis install
- An Anthropic, OpenAI, or Gemini API key — or [Ollama](https://ollama.com) for local models

---

## Setup

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

```bash
docker run -d --name redis-eg -p 6379:6379 redis:7-alpine

# Verify
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

### 4. Run

```bash
# Windows
python run.py

# macOS / Linux
uvicorn main:app --reload
```

The server starts at `http://localhost:8000`. On first startup it scrapes all categories and warms the cache — this takes a few minutes.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness check |
| `POST` | `/build` | Generate a PC build |
| `GET` | `/prices/{category}` | Get cached prices for a category |
| `GET` | `/admin/cache-status` | TTL and product count per cache key |
| `POST` | `/admin/scrape` | Force a full re-scrape |

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

Change `LLM_PROVIDER` in `.env` — no code changes needed:

```bash
LLM_PROVIDER=claude    # Anthropic Claude (default)
LLM_PROVIDER=gpt       # OpenAI GPT-4o
LLM_PROVIDER=gemini    # Google Gemini
LLM_PROVIDER=ollama    # Local model via Ollama (free, no API key)
```

### Using a specific model

```bash
# Override the default model for any provider
LLM_MODEL=gpt-4-turbo
LLM_MODEL=gemini-1.5-flash
LLM_MODEL=mistral        # any model you've pulled with ollama pull
```

### Running locally with Ollama

```bash
# Install Ollama from https://ollama.com then:
ollama pull llama3       # or mistral, deepseek-r1, etc.
ollama serve             # starts on http://localhost:11434

# Set in .env:
LLM_PROVIDER=ollama
LLM_MODEL=llama3
```

> **Note:** Local models work but produce lower-quality compatibility reasoning than frontier models. Recommended for development only.

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

Subclass `BaseScraper` in `scraper.py` and implement three methods:

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

Then add it to `SCRAPERS` in `main.py`:

```python
SCRAPERS = [
    EGPricesScraper(),
    BTechScraper(),   # ← add here
]
```

Results from all scrapers are automatically merged and deduplicated.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | If using Claude | — | Anthropic API key |
| `OPENAI_API_KEY` | If using GPT | — | OpenAI API key |
| `GEMINI_API_KEY` | If using Gemini | — | Google API key |
| `LLM_PROVIDER` | No | `claude` | Active LLM provider |
| `LLM_MODEL` | No | Provider default | Override the model name |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection URL |

---

## License

MIT


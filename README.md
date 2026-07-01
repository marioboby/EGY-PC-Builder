# EG PC Builder 🖥️🇪🇬

**EG PC Builder** is an AI-powered PC building assistant specifically tailored for the Egyptian market. It scrapes live pricing data from local vendors (via EGPrices), caches it in Redis for rapid retrieval, and uses advanced Large Language Models (LLMs) to automatically generate optimal, compatible PC builds based on your exact budget, use case, and priorities.

## ✨ Why this project is useful

Building a PC in Egypt involves navigating rapidly changing prices and availability across different stores. This tool automates the hardest parts:

* **Real-Time Egyptian Prices:** Automatically scrapes and merges live component prices from EGPrices.com.
* **Smart AI Recommendations:** Uses LLMs (Gemini, Claude, GPT, or local Ollama models) to pick the best parts while guaranteeing socket compatibility, bottleneck avoidance, and budget adherence.
* **Flexible Priorities:** Optimize for "Max Performance", "Best Value", "Future-Proofing", or "Quiet & Cool".
* **Complete Build Suggestions:** Generates not just the parts list, but also feasibility reports, alternative parts, and future upgrade paths.

## 🛠️ Tech Stack

* **Backend:** Python, FastAPI, Playwright (for asynchronous web scraping), Redis (for caching), and `google-genai` / `openai` / `anthropic` SDKs.
* **Frontend:** React 19, Vite, and custom CSS for a sleek, responsive UI.

## 🚀 Getting Started

### Prerequisites

Before you begin, ensure you have the following installed:

* **Node.js** (v18+ recommended)
* **Python** (v3.10+ recommended)
* **Redis server** (running locally on default port `6379`)

### 1. Backend Setup

1. Navigate to the backend directory:
```bash
cd backend

```


2. Install the required Python packages:
```bash
pip install -r requirements.txt

```


3. Install Playwright browsers (required for scraping):
```bash
playwright install chromium

```


4. Create a `.env` file in the `backend/` directory and configure your preferred LLM provider. By default, the app uses Google's Gemini, but you can configure others:
```env
# Set provider: "gemini", "gpt", "claude", or "ollama"
LLM_PROVIDER=gemini 

# API Keys (Provide the one matching your LLM_PROVIDER)
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

```


5. Start your local Redis server if it isn't running already.
6. Start the backend API:
```bash
python run.py

```


*The backend will start on `http://localhost:8000`.*

### 2. Frontend Setup

1. Open a new terminal and navigate to the frontend directory:
```bash
cd frontend

```


2. Install the Node dependencies:
```bash
npm install

```


3. Start the Vite development server:
```bash
npm run dev

```


4. Open your browser and navigate to the local URL provided by Vite (usually `http://localhost:5173`).

### Usage Example

1. Open the frontend application in your browser.
2. Enter your **Budget** in EGP (e.g., `35000`).
3. Select your **Primary Use Case** (e.g., *Gaming 1440p*).
4. Choose a **Build Priority** (e.g., *Best Value*).
5. Add any optional notes (e.g., *"Prefer AMD CPU, need WiFi"*).
6. Click **Generate My Build**. The backend will fetch the latest cached prices, query the LLM, and return a complete, itemized build with total costs and store links!

## ❓ Where to get help

* **Issues & Bugs:** If you encounter a bug or have a feature request, please [open an issue](https://www.google.com/search?q=../../issues) on the GitHub repository.
* **Redis Issues:** Ensure Redis is running on port `6379`. You can check the cache status by visiting the backend diagnostic endpoint at `http://localhost:8000/admin/cache-status`.
* **Empty Scrapes:** If EGPrices updates their DOM structure, the CSS selectors in `backend/scraper.py` might need updating.

## 🤝 Who maintains and contributes

This project is actively maintained. We welcome contributions from the community!

**To contribute:**

1. Fork the repository.
2. Create a new branch for your feature (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add some amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

Please ensure your code follows the existing style, and test the backend scrapers thoroughly if you are modifying `scraper.py`.

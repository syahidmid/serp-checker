# 🔍 SERP Checker

A free, open-source SERP analysis tool built with Streamlit.

Fetch Google search results for any keyword, pick the URLs you want to analyse, then get deep competitor insights — outlines, search intent, and key facts — powered by OpenAI.

## Features

- **Geo-targeted search** — target any country, city, and language
- **Device toggle** — mobile or desktop results
- **URL picker** — select which top-10 results to deep-analyse
- **Scrapability check** — auto-pings each URL before analysis
- **AI competitor analysis** — extracts H1/H2/H3 outline, search intent, and 3 key facts per page
- **SERP intent summary** — overall intent across all selected results
- **Export** — download as CSV or Markdown report

## Requirements

- Python 3.9+
- [Serper.dev](https://serper.dev) API key (free tier available)
- [OpenAI](https://platform.openai.com) API key
- [Anthropic](https://console.anthropic.com) API key

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/syahidmid/serp-checker.git
cd serp-checker

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your API keys
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml with your keys

# 4. Run the app
streamlit run app.py
```

## API Keys

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in:

| Key | Where to get it |
|---|---|
| `SERPER_API_KEY` | [serper.dev](https://serper.dev) |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |

## How It Works

1. **Phase 1 — Fetch**: Enter a keyword → get top 10 Google results via Serper.dev API
2. **Phase 2 — Pick**: Select which URLs to analyse (problem URLs like 403/404 are flagged)
3. **Phase 3 — Analyse**: Each selected URL is scraped and sent to OpenAI for structured analysis

## Tech Stack

- [Streamlit](https://streamlit.io) — UI framework
- [Serper.dev](https://serper.dev) — Google SERP API
- [OpenAI GPT-4o-mini](https://platform.openai.com) — competitor page analysis
- [Anthropic Claude](https://anthropic.com) — SERP intent summary
- [markdownify](https://github.com/matthewwithanm/python-markdownify) — HTML to Markdown conversion
- [pycountry](https://github.com/flyingcircus-io/pycountry) + [geonamescache](https://github.com/yaph/geonamescache) — country/city selectors

## License

MIT — free to use, modify, and distribute.

---

Built by [Muhammad Syahid](https://syahidmuhammad.com)

"""
serp_module.py

Changelog:
- REMOVED: extract_competitor_data() using OpenAI web_search tool (expensive)
- REPLACED: Now uses scrape_to_markdown (markdownify) + Claude completion
- Pattern adopted from SERP_Checker.py which is already proven working
- MIGRATED: OpenAI → Anthropic Claude (claude-sonnet-4-5)
"""

import streamlit as st
import re
import json
from utils.serper_client import get_serper_results
from utils.claude_helper import run_openai_completion
from utils.scraper_with_markdownify import scrape_to_markdown


# ── SERP Fetching ─────────────────────────────────────────────────────────────

def run_serp_analysis(keyword: str, location="Jakarta, Indonesia", lang="id",
                      gl: str = None, hl: str = None, num: int = 4,
                      device: str = "mobile"):
    """
    Perform real SERP lookup via Serper.dev API.
    """
    api_key = st.secrets["SERPER_API_KEY"]
    serp_data = get_serper_results(api_key, keyword, location, lang,
                                   gl=gl, hl=hl, num=max(num, 4), device=device)

    if not serp_data:
        st.warning("⚠️ No organic results found.")
        return []

    parsed_data = []
    for i, item in enumerate(serp_data[:num], start=1):
        parsed_data.append({
            "rank":    i,
            "domain":  item.get("link", "").split("/")[2] if "link" in item else "",
            "title":   item.get("title", "N/A"),
            "snippet": item.get("snippet", "N/A"),
            "url":     item.get("link", "")
        })

    return parsed_data


def analyze_serp_intent(serp_results: list, model="claude-sonnet-4-5"):
    """
    Analyze the SERP results to infer dominant search intent.
    """
    serp_text = "\n".join(
        [f"{res['title']}: {res['snippet']}" for res in serp_results if 'title' in res]
    )

    prompt = f"""
Analyze the following Google search results and infer the dominant search intent.
Then summarize it into two parts:
1. Type of search intent (e.g., informational, transactional, navigational, or commercial investigation)
2. A short explanation (max two sentences) describing what users likely want to achieve.

Results:
{serp_text}
"""
    return run_openai_completion(prompt, model=model)


def run_serp_analysis_full(keyword: str, location="Jakarta, Indonesia", lang="id",
                           gl: str = None, hl: str = None, num: int = 4,
                           device: str = "mobile", model="claude-sonnet-4-5"):
    """
    Wrapper: Fetch real SERP + analyze intent with Claude.
    """
    serp_data = run_serp_analysis(keyword, location, lang, gl=gl, hl=hl, num=num, device=device)
    if not serp_data:
        return [], "No SERP data available."
    intent_summary = analyze_serp_intent(serp_data, model)
    return serp_data, intent_summary


# ── Competitor Extraction ─────────────────────────────────────────────────────

def extract_competitor_data(url: str, model="claude-sonnet-4-5",
                            prefetched_markdown: str = None) -> dict:
    """
    Scrape URL to Markdown via markdownify, then send to Claude for
    structured analysis (outline, intent, summary).

    Args:
        url: Target URL
        model: Claude model to use
        prefetched_markdown: Optional pre-scraped markdown (avoids double scraping)

    Returns:
        dict: {outline, intent, intent_explanation, summary}
    """
    # ── Step 1: Scrape (or use prefetched) ───────────────────────────────────
    if prefetched_markdown is not None:
        markdown_content = prefetched_markdown
    else:
        result = scrape_to_markdown(url)

        if not result["status_ok"]:
            return {
                "outline":             f"[ERROR] {result['status_label']}",
                "intent":              "Unknown",
                "intent_explanation":  "",
                "summary":             [],
            }

        markdown_content = result["markdown"]

    if not markdown_content.strip():
        return {
            "outline":             "[ERROR] No content found after scraping.",
            "intent":              "Unknown",
            "intent_explanation":  "",
            "summary":             [],
        }

    # Truncate to avoid token overflow (~12k chars ≈ ~3k tokens)
    truncated = markdown_content[:12000]

    # ── Step 2: Claude analysis (standard completion) ─────────────────────────
    prompt = f"""
Analyze the following article content (in Markdown format) from a competitor page.

Your tasks:
1. Extract ONLY the article outline (H1, H2, H3 headings).
2. Identify the search intent: informational, commercial investigation, transactional, or navigational.
3. Extract 3 key factual bullet points. Focus on:
   - Official application/website names being discussed
   - Managing institutions, brands, or organizations
   - Main functions, benefits, or features
   - Access methods or usage steps
   - Specific locations, prices, or concrete details

Return JSON only in this exact format:

{{
  "outline": "text outline here...",
  "intent": "Commercial Investigation",
  "intent_explanation": "One short sentence",
  "summary": [
    "Factual bullet point 1 about specific names/brands",
    "Factual bullet point 2 about features/functions",
    "Factual bullet point 3 about access/usage/details"
  ]
}}

IMPORTANT:
- Extract ONLY factual information (names, places, numbers, specific features)
- Do NOT include generic statements
- Output JSON ONLY. No commentary. No code block formatting.

Article content:
{truncated}
"""

    response = run_openai_completion(prompt, model=model, temperature=0.2)
    cleaned  = clean_json(response)

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Fallback: try extracting JSON object from text
    json_match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except Exception:
            pass

    # Final fallback
    return {
        "outline":             cleaned,
        "intent":              "Unknown",
        "intent_explanation":  "",
        "summary":             [],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def clean_json(text: str) -> str:
    if not text:
        return text
    text = re.sub(r"```json(.*?)```", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"```(.*?)```",     r"\1", text, flags=re.DOTALL)
    text = text.replace("```", "").replace("`", "")
    return text.strip()

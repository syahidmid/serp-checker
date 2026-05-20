import streamlit as st

st.set_page_config(
    page_title="SERP Checker",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

import pandas as pd
import pycountry
import geonamescache
import requests
from datetime import datetime
from utils.serper_client import get_serper_results
from utils.serp_module import analyze_serp_intent
from utils.scraper_with_markdownify import scrape_to_markdown
from openai import OpenAI
import json
import re

def _get_openai_client() -> OpenAI:
    api_key = st.secrets.get("OPENAI_API_KEY") or None
    return OpenAI(api_key=api_key)

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

st.title("🔍 SERP Checker")
st.caption("Fetch Google results, pick the URLs you want, then deep-analyse.")


def _fetch_raw_serp(keyword: str, location: str, gl: str, hl: str,
                    num: int, device: str) -> list:
    api_key = st.secrets["SERPER_API_KEY"]
    raw = get_serper_results(api_key, keyword,
                             location=location, lang=hl,
                             gl=gl, hl=hl, num=num, device=device)
    parsed = []
    for i, item in enumerate(raw[:num], start=1):
        link = item.get("link", "")
        parsed.append({
            "rank":    i,
            "domain":  link.split("/")[2] if link else "",
            "title":   item.get("title", "N/A"),
            "snippet": item.get("snippet", "N/A"),
            "url":     link,
        })
    return parsed


@st.cache_data
def _load_countries() -> list[dict]:
    countries = [
        {"name": c.name, "alpha_2": c.alpha_2.lower()}
        for c in pycountry.countries
    ]
    return sorted(countries, key=lambda x: x["name"])


@st.cache_data
def _load_cities(country_alpha2_upper: str) -> list[str]:
    gc = geonamescache.GeonamesCache()
    cities = gc.get_cities()
    result = sorted(
        {c["name"] for c in cities.values()
         if c.get("countrycode") == country_alpha2_upper}
    )
    return result if result else ["(no cities found)"]


@st.cache_data
def _load_languages() -> list[dict]:
    langs = []
    for lang in pycountry.languages:
        alpha_2 = getattr(lang, "alpha_2", None)
        if alpha_2:
            langs.append({
                "label": f"{lang.name} ({alpha_2})",
                "alpha_2": alpha_2.lower(),
            })
    return sorted(langs, key=lambda x: x["label"])


def extract_competitor_data(url: str, model: str = "gpt-4o-mini",
                            prefetched_markdown: str = None) -> dict:
    if prefetched_markdown is not None:
        markdown_content = prefetched_markdown
    else:
        result = scrape_to_markdown(url)
        if not result["status_ok"]:
            return {
                "outline": f"[ERROR] {result['status_label']}",
                "intent": "Unknown",
                "intent_explanation": "",
                "summary": [],
            }
        markdown_content = result["markdown"]

    if not markdown_content.strip():
        return {
            "outline": "[ERROR] No content found after scraping.",
            "intent": "Unknown",
            "intent_explanation": "",
            "summary": [],
        }

    truncated = markdown_content[:12000]

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

    response = _get_openai_client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    raw = response.choices[0].message.content or ""
    cleaned = re.sub(r"```json|```", "", raw).strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    json_match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except Exception:
            pass

    return {
        "outline": cleaned,
        "intent": "Unknown",
        "intent_explanation": "",
        "summary": [],
    }


def _fmt_facts(facts: list) -> str:
    return "\n".join(f"• {f}" for f in facts) if facts else "—"


def _build_markdown_report(keyword, location, gl, hl, device, run_at,
                            serp_results, competitor_data, serp_summary):
    lines = [
        "# SERP Analysis Report", "",
        f"**Primary Keyword:** {keyword}  ",
        f"**Location:** {location}  ",
        f"**Country (gl):** {gl}  |  **Language (hl):** {hl}  |  **Device:** {device}  ",
        f"**Generated:** {run_at}",
        "", "---", "",
    ]

    if serp_summary:
        lines += ["## 🧩 SERP Intent Summary", "", serp_summary, "", "---", ""]

    lines += [
        "## 📊 Top Results", "",
        "| # | Domain | Title | Snippet |",
        "|---|--------|-------|---------|",
    ]
    for res in serp_results:
        t = res.get("title", "").replace("|", "\\|")
        s = res.get("snippet", "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {res.get('rank','')} | {res.get('domain','')} | {t} | {s} |")

    lines += ["", "---", "", "## 🕵️ Competitor Analysis", ""]

    for i, (res, comp) in enumerate(zip(serp_results, competitor_data), 1):
        intent_line = comp.get("intent", "")
        if comp.get("intent_explanation"):
            intent_line += f" — {comp['intent_explanation']}"

        lines += [
            f"### {i}. {res.get('domain', '')}",
            f"**URL:** {res.get('url', '')}  ",
            f"**Title:** {res.get('title', '')}  ",
            f"**Snippet:** {res.get('snippet', '')}  ",
            "",
        ]
        if intent_line:
            lines += [f"**Intent:** {intent_line}", ""]
        if comp.get("outline"):
            lines += ["**Outline:**", "", "```", comp["outline"].strip(), "```", ""]
        if comp.get("summary"):
            lines += ["**Key Facts:**", ""]
            lines += [f"- {f}" for f in comp["summary"]]
            lines.append("")
        lines += ["---", ""]

    return "\n".join(lines)


def _ping_url(url: str, timeout: int = 5) -> dict:
    try:
        r = requests.head(url, headers=_DEFAULT_HEADERS, timeout=timeout,
                          allow_redirects=True)
        code = r.status_code
        if code in (405, 501):
            r = requests.get(url, headers=_DEFAULT_HEADERS, timeout=timeout,
                             allow_redirects=True, stream=True)
            r.close()
            code = r.status_code
    except requests.exceptions.Timeout:
        return {"status_code": None, "badge": "⏱️ Timeout"}
    except requests.exceptions.ConnectionError:
        return {"status_code": None, "badge": "🔌 No connection"}
    except Exception:
        return {"status_code": None, "badge": "❓ Unknown"}

    if code == 200:
        return {"status_code": code, "badge": "✅ OK"}
    elif code in (301, 302, 303, 307, 308):
        return {"status_code": code, "badge": f"🔄 Redirect ({code})"}
    elif code == 403:
        return {"status_code": code, "badge": "⚠️ Blocked (403)"}
    elif code == 429:
        return {"status_code": code, "badge": "⚠️ Rate limited (429)"}
    elif code == 404:
        return {"status_code": code, "badge": "❌ Not found (404)"}
    elif code == 410:
        return {"status_code": code, "badge": "❌ Gone (410)"}
    elif 500 <= code < 600:
        return {"status_code": code, "badge": f"❌ Server error ({code})"}
    else:
        return {"status_code": code, "badge": f"❓ {code}"}


def _ping_all(urls: list[str]) -> dict:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(_ping_url, url): url for url in urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                results[url] = future.result()
            except Exception:
                results[url] = {"status_code": None, "badge": "❓ Unknown"}
    return results


_state_keys = [
    "sc_raw_serp", "sc_serp_results", "sc_competitor_data",
    "sc_serp_summary", "sc_ping_results",
    "sc_keyword", "sc_location", "sc_gl", "sc_hl", "sc_device", "sc_run_at",
    "sc_phase",
]
for k in _state_keys:
    if k not in st.session_state:
        st.session_state[k] = None


with st.expander("⚙️ Search Settings", expanded=True):

    col_kw, col_country = st.columns([3, 3])

    with col_kw:
        keyword = st.text_input("Primary Keyword",
                                placeholder="e.g. modal usaha toko skincare")

    with col_country:
        all_countries = _load_countries()
        country_names = [c["name"] for c in all_countries]
        default_country_idx = next(
            (i for i, c in enumerate(all_countries) if c["alpha_2"] == "id"), 0
        )
        selected_country_name = st.selectbox(
            "Country", country_names, index=default_country_idx
        )
        selected_country = next(
            c for c in all_countries if c["name"] == selected_country_name
        )
        gl = selected_country["alpha_2"]

    col_city, col_lang, col_dev = st.columns([3, 2, 1])

    with col_city:
        city_list = _load_cities(gl.upper())
        selected_city = st.selectbox("City / Region", ["Jakarta"] + city_list)

    with col_lang:
        all_languages = _load_languages()
        lang_labels   = [l["label"] for l in all_languages]
        default_lang_idx = next(
            (i for i, l in enumerate(all_languages) if l["alpha_2"] == "id"), 0
        )
        lang_label = st.selectbox("Language (hl)", lang_labels, index=default_lang_idx)
        hl = next(l["alpha_2"] for l in all_languages if l["label"] == lang_label)

    with col_dev:
        device = st.selectbox("Device", ["mobile", "desktop"], index=0)

    if selected_city == "(country-level)":
        location_str = selected_country_name
    else:
        location_str = f"{selected_city}, {selected_country_name}"

    st.caption(
        f"📍 `{location_str}` · gl=`{gl}` · hl=`{hl}` · device=`{device}`"
    )


st.markdown("---")
fetch_btn = st.button("🔎 Fetch SERP Results (top 10)",
                      use_container_width=True, type="primary")

if fetch_btn:
    if not keyword.strip():
        st.warning("⚠️ Please enter a keyword first.")
        st.stop()

    with st.spinner(f"🔍 Fetching top 10 results for '{keyword}'…"):
        raw = _fetch_raw_serp(keyword, location=location_str,
                              gl=gl, hl=hl, num=10, device=device)

    if not raw:
        st.error("❌ No results returned. Check keyword or API key.")
        st.stop()

    st.session_state.update({
        "sc_raw_serp":        raw,
        "sc_serp_results":    None,
        "sc_competitor_data": None,
        "sc_serp_summary":    None,
        "sc_ping_results":    None,
        "sc_keyword":         keyword,
        "sc_location":        location_str,
        "sc_gl":              gl,
        "sc_hl":              hl,
        "sc_device":          device,
        "sc_run_at":          datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sc_phase":           "pick",
    })

    with st.spinner("🔎 Checking which URLs are scrapable…"):
        urls = [r["url"] for r in raw if r.get("url")]
        st.session_state["sc_ping_results"] = _ping_all(urls)


raw_serp = st.session_state.get("sc_raw_serp")

if raw_serp and st.session_state.get("sc_phase") == "pick":
    st.markdown("### 🗂️ Pick URLs to Analyse")
    st.caption("Check the URLs you want to deep-analyse, then click the button below.")

    ping_results = st.session_state.get("sc_ping_results") or {}
    _WARN_CODES = {403, 404, 410}

    checked_indices = []
    default_checked_count = 0
    for i, res in enumerate(raw_serp):
        rank        = res.get("rank", i + 1)
        domain      = res.get("domain", "")
        title       = res.get("title", "")
        url         = res.get("url", "")
        ping        = ping_results.get(url, {})
        badge       = ping.get("badge", "⏳ Checking…")
        status_code = ping.get("status_code")

        is_problematic = status_code in _WARN_CODES
        default_val = (not is_problematic) and (default_checked_count < 4)
        if default_val:
            default_checked_count += 1

        col_cb, col_info, col_badge = st.columns([1, 11, 2])
        with col_cb:
            checked = st.checkbox(f"Select result {rank}", value=default_val,
                                  key=f"sc_pick_{i}",
                                  label_visibility="collapsed")
        with col_info:
            st.markdown(
                f"**{rank}.** [{title}]({url})  \n"
                f"<small style='color:grey'>{domain} · {url}</small>",
                unsafe_allow_html=True,
            )
        with col_badge:
            st.markdown(
                f"<div style='padding-top:6px;font-size:0.8rem'>{badge}</div>",
                unsafe_allow_html=True,
            )

        if checked and is_problematic:
            st.warning(
                f"**{domain}** may not be scrapable ({badge}). "
                f"You can still include it, but the result will likely be empty.",
                icon="⚠️",
            )

        if checked:
            checked_indices.append(i)

    st.markdown("---")
    analyse_btn = st.button(
        f"🚀 Analyse {len(checked_indices)} selected URL(s)",
        use_container_width=True,
        type="primary",
        disabled=len(checked_indices) == 0,
    )

    if analyse_btn:
        selected = [raw_serp[i] for i in checked_indices]
        competitor_data = []

        with st.status("⚙️ Running analysis…", expanded=True) as status:

            st.write("🧠 Analysing overall SERP intent…")
            serp_summary = analyze_serp_intent(selected)
            st.write("✅ SERP intent done.")

            for idx, res in enumerate(selected, 1):
                domain = res.get("domain", f"site {idx}")
                url    = res.get("url", "")

                st.write(f"🌐 `[{idx}/{len(selected)}]` Scraping **{domain}**…")
                scrape_result = scrape_to_markdown(url)

                if not scrape_result["status_ok"]:
                    st.write(f"⚠️ `[{idx}/{len(selected)}]` **{domain}** — {scrape_result['status_label']}")
                    competitor_data.append({
                        "outline": f"[ERROR] {scrape_result['status_label']}",
                        "intent": "Unknown",
                        "intent_explanation": "",
                        "summary": [],
                    })
                    continue

                st.write(f"🤖 `[{idx}/{len(selected)}]` Sending **{domain}** to OpenAI…")
                comp = extract_competitor_data(url, prefetched_markdown=scrape_result["markdown"])
                competitor_data.append(comp)
                st.write(f"✅ `[{idx}/{len(selected)}]` **{domain}** done.")

            status.update(label="✅ Analysis complete!", state="complete", expanded=False)

        st.session_state.update({
            "sc_serp_results":    selected,
            "sc_competitor_data": competitor_data,
            "sc_serp_summary":    serp_summary,
            "sc_phase":           "done",
        })
        st.rerun()


if st.session_state.get("sc_phase") == "done":
    serp_results    = st.session_state["sc_serp_results"]
    competitor_data = st.session_state["sc_competitor_data"]
    serp_summary    = st.session_state["sc_serp_summary"]
    kw_saved        = st.session_state["sc_keyword"]
    loc_saved       = st.session_state["sc_location"]
    gl_saved        = st.session_state["sc_gl"]
    hl_saved        = st.session_state["sc_hl"]
    dev_saved       = st.session_state["sc_device"]
    run_at          = st.session_state["sc_run_at"]

    st.markdown("---")

    if serp_summary:
        st.markdown("### 🧩 SERP Intent Summary")
        st.markdown(serp_summary)
        st.markdown("---")

    if st.button("↩️ Re-pick URLs", help="Go back to URL selector"):
        st.session_state["sc_phase"] = "pick"
        st.rerun()

    st.markdown("---")

    rows = []
    for i, res in enumerate(serp_results):
        comp = competitor_data[i] if i < len(competitor_data) else {}
        intent_txt = comp.get("intent", "")
        if comp.get("intent_explanation"):
            intent_txt += f" — {comp['intent_explanation']}"
        rows.append({
            "#":          res.get("rank", i + 1),
            "Domain":     res.get("domain", ""),
            "Title":      res.get("title", ""),
            "Snippet":    res.get("snippet", ""),
            "Intent":     intent_txt,
            "Outline":    comp.get("outline", ""),
            "Key Facts":  _fmt_facts(comp.get("summary", [])),
            "URL":        res.get("url", ""),
        })

    slug = kw_saved.replace(" ", "_").lower()

    markdown_report = _build_markdown_report(
        keyword=kw_saved, location=loc_saved, gl=gl_saved, hl=hl_saved,
        device=dev_saved, run_at=run_at,
        serp_results=serp_results, competitor_data=competitor_data,
        serp_summary=serp_summary,
    )

    tab_table, tab_md = st.tabs(["📊 Table View", "📝 Markdown View"])

    with tab_table:
        st.markdown(
            f"**Keyword:** `{kw_saved}` &nbsp;·&nbsp; "
            f"**Location:** `{loc_saved}` &nbsp;·&nbsp; "
            f"**gl:** `{gl_saved}` &nbsp;·&nbsp; "
            f"**hl:** `{hl_saved}` &nbsp;·&nbsp; "
            f"**Device:** `{dev_saved}` &nbsp;·&nbsp; "
            f"**Generated:** {run_at}"
        )

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
            column_config={
                "#":         st.column_config.NumberColumn(width="small"),
                "Domain":    st.column_config.TextColumn(width="medium"),
                "Title":     st.column_config.TextColumn(width="large"),
                "Snippet":   st.column_config.TextColumn(width="large"),
                "Intent":    st.column_config.TextColumn(width="medium"),
                "Outline":   st.column_config.TextColumn(width="large"),
                "Key Facts": st.column_config.TextColumn(width="large"),
                "URL":       st.column_config.LinkColumn(width="medium"),
            },
        )

        df_export  = pd.DataFrame(rows)
        csv_header = (
            f"Primary Keyword,{kw_saved}\n"
            f"Location,{loc_saved}\n"
            f"Country (gl),{gl_saved}\n"
            f"Language (hl),{hl_saved}\n"
            f"Device,{dev_saved}\n"
            f"Generated,{run_at}\n\n"
        )
        st.download_button(
            label="📥 Download CSV",
            data=(csv_header + df_export.to_csv(index=False)).encode("utf-8"),
            file_name=f"serp_{slug}_{run_at[:10]}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with tab_md:
        st.markdown(markdown_report)
        st.markdown("---")
        st.text_area("Raw Markdown (copy-paste ready)",
                     value=markdown_report, height=400)

        word_count  = len(markdown_report.split())
        token_est   = int(word_count * 1.33)
        st.caption(f"📝 {word_count:,} words (~{token_est:,} tokens)")
        st.download_button(
            label="📥 Download Markdown",
            data=markdown_report.encode("utf-8"),
            file_name=f"serp_{slug}_{run_at[:10]}.md",
            mime="text/markdown",
            use_container_width=True,
        )

elif not raw_serp:
    st.info("💡 Enter a keyword and click **Fetch SERP Results** to get started.")

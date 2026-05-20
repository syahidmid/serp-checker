import requests
import streamlit as st

@st.cache_data(ttl=18000)
def get_serper_results(api_key: str, keyword: str,
                       location: str = "Jakarta, Indonesia",
                       lang: str = "id",
                       gl: str = None,
                       hl: str = None,
                       num: int = 10,
                       device: str = "mobile"):
    """
    Fetch organic SERP results from Serper.dev API.

    Args:
        api_key:  Serper.dev API key
        keyword:  Search query
        location: Human-readable location string (e.g. "Jakarta, Indonesia")
        lang:     Legacy shorthand — sets both gl and hl when not supplied explicitly
        gl:       Country code for result targeting (e.g. "id", "us", "sg")
        hl:       Interface / result language code (e.g. "id", "en")
        num:      Number of organic results to return (max 10)
        device:   Device type — "mobile" or "desktop" (default: "mobile")
    """
    resolved_gl = gl if gl else lang
    resolved_hl = hl if hl else lang

    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {
        "q": keyword,
        "location": location,
        "gl": resolved_gl,
        "hl": resolved_hl,
        "num": num,
        "device": device,
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 403:
        st.error("🚨 Invalid Serper.dev API Key!")
        st.stop()
    if response.status_code != 200:
        st.error(f"❌ Error {response.status_code}: {response.text}")
        st.stop()

    return response.json().get("organic", [])

import os
import streamlit as st
import anthropic

# ----------------------------
# 🧠 Helper: Get Anthropic Client
# ----------------------------
def get_client():
    """
    Returns an authenticated Anthropic client.
    Priority:
    1. st.secrets["ANTHROPIC_API_KEY"]
    2. os.environ["ANTHROPIC_API_KEY"]
    """

    api_key = None

    # Cek Streamlit secrets
    if "ANTHROPIC_API_KEY" in st.secrets:
        api_key = st.secrets["ANTHROPIC_API_KEY"]

    # Fallback ke environment variable
    elif "ANTHROPIC_API_KEY" in os.environ:
        api_key = os.environ["ANTHROPIC_API_KEY"]

    # Kalau gak ada sama sekali
    if not api_key:
        st.error("❌ ANTHROPIC_API_KEY not found. Please set it in `.streamlit/secrets.toml` or environment variables.")
        raise ValueError("ANTHROPIC_API_KEY not found.")

    return anthropic.Anthropic(api_key=api_key)


# ----------------------------
# ⚙️ Helper: Run Claude Request
# ----------------------------
def run_openai_completion(prompt, model="claude-sonnet-4-5", temperature=0.7):
    """
    Sends a text completion request to the Anthropic Claude API and returns the content.
    Function name kept as run_openai_completion for backward compatibility
    — all existing callers work without changes.
    """
    client = get_client()

    try:
        response = client.messages.create(
            model=model,
            max_tokens=8096,
            temperature=temperature,
            system="You are a helpful SEO writing assistant.",
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
        return response.content[0].text.strip()

    except Exception as e:
        st.error(f"⚠️ Anthropic Claude request failed: {e}")
        raise e

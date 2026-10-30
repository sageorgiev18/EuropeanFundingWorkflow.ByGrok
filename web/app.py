import json
from pathlib import Path

import pandas as pd
import streamlit as st

# Paths
REPO_ROOT = Path(__file__).parent.parent
DATA_FILE = REPO_ROOT / "data" / "eu_funding_tenders_matches.json"

st.set_page_config(page_title="EU Funding Workflow", layout="wide")

st.title("EU Funding Opportunities")
st.caption("Matching calls for tenders from the European Commission Funding & Tenders Portal")


@st.cache_data
def load_matches():
    if not DATA_FILE.exists():
        return pd.DataFrame(), {}
    with open(DATA_FILE, encoding="utf-8") as f:
        payload = json.load(f)
    matches = payload.get("matches", [])
    df = pd.DataFrame(matches)
    meta = {
        "profile": payload.get("profile"),
        "scraped_at": payload.get("scraped_at"),
        "count": payload.get("count", len(matches)),
    }
    return df, meta


df, meta = load_matches()

if df.empty:
    st.warning(
        "No data found. Run the scraper first:\n\n"
        "```bash\ncd scrapers\npython -m sources.eu_funding_tenders.scraper\n```"
    )
    st.stop()

# Sidebar filters
st.sidebar.header("Filters")
min_score = st.sidebar.slider("Minimum match score", 0.0, 1.0, 0.0, 0.05)
search = st.sidebar.text_input("Search title / summary", "")

filtered = df[df["match_score"] >= min_score].copy()
if search:
    mask = (
        filtered["title"].fillna("").str.contains(search, case=False)
        | filtered["summary"].fillna("").str.contains(search, case=False)
    )
    filtered = filtered[mask]

st.sidebar.metric("Showing", len(filtered))
st.sidebar.caption(f"Profile: {meta.get('profile', 'N/A')}")
st.sidebar.caption(f"Last scraped: {meta.get('scraped_at', 'N/A')[:19]}")

# Main metrics
col1, col2, col3 = st.columns(3)
col1.metric("Total matches", meta.get("count", 0))
col2.metric("After filters", len(filtered))
if not filtered.empty and "deadline" in filtered.columns:
    upcoming = filtered["deadline"].notna().sum()
    col3.metric("With deadline", int(upcoming))

# Table
st.subheader("Opportunities")
display_cols = [
    "title",
    "call_identifier",
    "match_score",
    "deadline",
    "matched_keywords",
    "url",
]
display_cols = [c for c in display_cols if c in filtered.columns]

st.dataframe(
    filtered[display_cols].sort_values("match_score", ascending=False),
    use_container_width=True,
    column_config={
        "url": st.column_config.LinkColumn("Portal link"),
        "match_score": st.column_config.NumberColumn("Score", format="%.2f"),
        "matched_keywords": st.column_config.ListColumn("Matched keywords"),
    },
)

# Detail expander
if not filtered.empty:
    st.subheader("Details")
    for _, row in filtered.sort_values("match_score", ascending=False).head(10).iterrows():
        with st.expander(f"{row.get('title', 'Untitled')}  —  score {row.get('match_score', 0):.2f}"):
            st.write(row.get("summary", "No summary"))
            if row.get("deadline"):
                st.write(f"**Deadline:** {row['deadline']}")
            if row.get("url"):
                st.markdown(f"[Open on portal]({row['url']})")
            if row.get("matched_keywords"):
                st.write("**Matched keywords:**", ", ".join(row["matched_keywords"]))

st.caption("Data source: EU Funding & Tenders Portal via official SEDIA Search API")

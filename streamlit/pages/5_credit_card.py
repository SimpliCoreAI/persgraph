"""💳 Credit Card Agent — Statement parsing and rewards optimization."""

import streamlit as st

st.set_page_config(page_title="Credit Card Agent", page_icon="💳", layout="wide")
st.title("💳 Credit Card Agent")
st.caption("Parse statements, track spend, optimize rewards.")
st.divider()

tab1, tab2, tab3 = st.tabs(["📄 Statements", "🏦 Cards & Benefits", "💡 Recommendations"])

# ── Tab 1: Statements ─────────────────────────────────────────────────────────
with tab1:
    st.markdown("### Upload Statement")
    uploaded = st.file_uploader("Credit card statement (PDF or CSV)", type=["pdf", "csv"])
    card_name = st.text_input("Card name", placeholder="e.g. Chase Sapphire, Amex Gold")

    if st.button("Parse Statement", type="primary", disabled=not uploaded):
        st.info("⚙️ Statement parsing — coming soon (Qwen2.5 via Ollama)")

    st.divider()
    st.markdown("### Spend Breakdown")
    st.info("📊 Transaction categories and charts will appear here after parsing.")

# ── Tab 2: Cards & Benefits ───────────────────────────────────────────────────
with tab2:
    st.markdown("### Your Cards")
    st.info("⚙️ Card benefits database — coming soon")

    st.markdown("### Add a Card")
    col1, col2 = st.columns(2)
    with col1:
        new_card = st.text_input("Card name")
        annual_fee = st.number_input("Annual fee ($)", min_value=0)
    with col2:
        dining_mult = st.number_input("Dining multiplier (x)", min_value=1.0, value=1.0, step=0.5)
        travel_mult = st.number_input("Travel multiplier (x)", min_value=1.0, value=1.0, step=0.5)
    notes = st.text_area("Other benefits / notes", height=60)

    if st.button("💾 Save Card", disabled=not new_card.strip()):
        st.info("⚙️ Card database — coming soon")

# ── Tab 3: Recommendations ────────────────────────────────────────────────────
with tab3:
    st.markdown("### Optimization Suggestions")
    st.info("⚙️ Recommendations engine — coming soon")

    query = st.text_input("Ask", placeholder="Which card should I use for my flight booking?")
    if st.button("Ask", disabled=not query.strip()):
        st.info("⚙️ CC Agent RAG query — coming soon")

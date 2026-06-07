"""💳 Credit Card Agent — Powered by Koko Finance MCP."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import streamlit as st
from second_brain.koko import (
    which_card_at_merchant, recommend_for_category,
    optimize_portfolio, compare_cards,
    check_merchant_benefits, get_card_details,
    search_cards, DEFAULT_PORTFOLIO
)

st.set_page_config(page_title="Credit Card Agent", page_icon="💳", layout="wide")
st.title("💳 Credit Card Agent")
st.caption("Powered by Koko Finance — 100+ US cards · No data leaves your device")
st.divider()

tab1, tab2, tab3, tab4 = st.tabs([
    "🏪 Which Card to Use",
    "📊 Portfolio Health",
    "🔍 Card Details",
    "🔎 Search Cards",
])

# ── Tab 1: Which Card to Use ──────────────────────────────────────────────────
with tab1:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🏪 At a Merchant")
        merchant = st.text_input("Merchant name", placeholder="e.g. Costco, Whole Foods, Delta")
        if st.button("Which card?", type="primary", disabled=not merchant.strip()):
            with st.spinner(f"Checking best card for {merchant}..."):
                try:
                    result = which_card_at_merchant(merchant.strip())
                    st.success("✅ Recommendation")
                    st.markdown(result["text"])
                except Exception as e:
                    st.error(f"Error: {e}")

        st.divider()
        st.markdown("### 🎁 Merchant Credits")
        merchant2 = st.text_input("Check credits at", placeholder="e.g. Saks Fifth Avenue, Uber")
        if st.button("Check benefits", disabled=not merchant2.strip()):
            with st.spinner("Checking card credits..."):
                try:
                    result = check_merchant_benefits(merchant2.strip())
                    st.info(result["text"])
                except Exception as e:
                    st.error(f"Error: {e}")

    with col2:
        st.markdown("### 🏷️ By Category")
        category = st.selectbox("Spending category", [
            "dining", "groceries", "travel", "gas",
            "streaming", "amazon", "shopping", "hotels",
            "flights", "entertainment", "pharmacy", "transit"
        ])
        if st.button("Best card for this", type="primary"):
            with st.spinner(f"Finding best card for {category}..."):
                try:
                    result = recommend_for_category(category)
                    st.success("✅ Recommendation")
                    st.markdown(result["text"])
                except Exception as e:
                    st.error(f"Error: {e}")

        st.divider()
        st.markdown("### ⚖️ Compare Cards")
        card_a = st.text_input("Card A", placeholder="e.g. amex-gold")
        card_b = st.text_input("Card B", placeholder="e.g. chase-sapphire-preferred")
        if st.button("Compare", disabled=not (card_a.strip() and card_b.strip())):
            with st.spinner("Comparing..."):
                try:
                    result = compare_cards([card_a.strip(), card_b.strip()])
                    st.markdown(result["text"])
                except Exception as e:
                    st.error(f"Error: {e}")

# ── Tab 2: Portfolio Health ───────────────────────────────────────────────────
with tab2:
    st.markdown("### 📊 Portfolio Health Check")
    st.caption(f"Analyzing: {', '.join(DEFAULT_PORTFOLIO)}")

    if st.button("🔍 Analyze My Portfolio", type="primary"):
        with st.spinner("Analyzing portfolio..."):
            try:
                result = optimize_portfolio()
                st.markdown(result["text"])
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()
    st.markdown("### 🃏 Card Details")
    card_name = st.text_input("Card ID", placeholder="e.g. amex-gold, chase-sapphire-preferred")
    if st.button("Get Details", disabled=not card_name.strip()):
        with st.spinner("Loading card details..."):
            try:
                result = get_card_details(card_name.strip())
                st.markdown(result["text"])
            except Exception as e:
                st.error(f"Error: {e}")

# ── Tab 3: Card Details ───────────────────────────────────────────────────────
with tab3:
    st.markdown("### 🃏 Your Cards")
    st.caption("Click any card to see full details")

    for card_id in DEFAULT_PORTFOLIO:
        if st.button(f"📋 {card_id}", key=f"card_{card_id}"):
            with st.spinner(f"Loading {card_id}..."):
                try:
                    result = get_card_details(card_id)
                    st.markdown(result["text"])
                except Exception as e:
                    st.error(f"Error: {e}")

# ── Tab 4: Search Cards ───────────────────────────────────────────────────────
with tab4:
    st.markdown("### 🔎 Search 100+ US Cards")
    query = st.text_input("Search", placeholder="e.g. best travel card, no foreign transaction fee, 5x dining")
    max_fee = st.slider("Max annual fee ($)", 0, 700, 700)
    if st.button("Search", type="primary", disabled=not query.strip()):
        with st.spinner("Searching..."):
            try:
                fee = None if max_fee == 700 else max_fee
                result = search_cards(query.strip(), max_annual_fee=fee)
                st.markdown(result["text"])
            except Exception as e:
                st.error(f"Error: {e}")

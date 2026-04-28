"""Streamlit text chat for 3am Mom.

Secondary surface — the headline UX is the custom voice frontend at
voice/static/index.html, served by voice/server.py. This Streamlit chat is
text-only, useful for typed-input demos and as the entry point the eval
suite shares (evals/run_evals.py also calls Agent.turn).
"""
import time

import streamlit as st

from src.agent import Agent

st.set_page_config(page_title="3am Mom", page_icon="🌙", layout="centered")

st.markdown(
    """
<style>
.escalation-banner {background: #b91c1c; color: white; padding: 1rem; border-radius: .5rem; margin: 1rem 0;}
.lang-chip {display:inline-block; background:#e0e7ff; padding:.25rem .5rem; border-radius:.25rem; font-size:.85rem; margin-bottom:.5rem;}
.rtl {direction: rtl; text-align: right;}
.product-card {border:1px solid #e5e7eb; border-radius:.5rem; padding:1rem; margin:.5rem 0;}
</style>
""",
    unsafe_allow_html=True,
)

st.title("3am Mom")
st.caption("Text chat. For the voice surface, run `uvicorn voice.server:app` and open http://localhost:8000.")

if "agent" not in st.session_state:
    st.session_state.agent = Agent()
if "history" not in st.session_state:
    st.session_state.history = []

user_text = st.chat_input("Ask 3am Mom...")
if user_text:
    with st.spinner("Thinking..."):
        t0 = time.time()
        resp = st.session_state.agent.turn(user_text)
        latency = time.time() - t0
    st.session_state.history.append((user_text, resp, latency))

for user_text, resp, latency in reversed(st.session_state.history):
    rtl_user = "rtl" if any("؀" <= c <= "ۿ" for c in user_text) else ""
    rtl_resp = "rtl" if any("؀" <= c <= "ۿ" for c in resp.response_text) else ""
    with st.chat_message("user"):
        st.markdown(f'<div class="{rtl_user}">{user_text}</div>', unsafe_allow_html=True)
    with st.chat_message("assistant"):
        st.markdown(
            f'<span class="lang-chip">Detected: {resp.user_input_language} → {resp.response_language}</span>',
            unsafe_allow_html=True,
        )
        if resp.escalation and resp.escalation.triggered:
            triggers = ", ".join(resp.escalation.triggers)
            st.markdown(
                f'<div class="escalation-banner"><b>⚠ Medical attention needed</b><br>{resp.escalation.advice}<br>'
                f'<small>NICE NG143 categories: {triggers}</small></div>',
                unsafe_allow_html=True,
            )
        st.markdown(f'<div class="{rtl_resp}">{resp.response_text}</div>', unsafe_allow_html=True)
        if resp.products_recommended:
            st.markdown("**Suggested products**")
            for r in resp.products_recommended:
                p = r.product
                with st.container():
                    st.markdown(
                        f'<div class="product-card"><b>{p.name_en}</b> · AED {p.price_aed:.0f}<br>'
                        f'<small>{p.description_en}</small><br>'
                        f'<a href="#">View on Mumzworld</a></div>',
                        unsafe_allow_html=True,
                    )
        st.caption(f"Response in {latency:.2f}s · confidence {resp.confidence:.2f}")

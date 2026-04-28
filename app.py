"""Streamlit chat UI for 3am Mom — text by default, voice via st.audio_input."""
import time
import streamlit as st
from src.agent import Agent, turn_voice

st.set_page_config(page_title="3am Mom", page_icon="🌙", layout="centered")

st.markdown("""
<style>
.escalation-banner {background: #b91c1c; color: white; padding: 1rem; border-radius: .5rem; margin: 1rem 0;}
.lang-chip {display:inline-block; background:#e0e7ff; padding:.25rem .5rem; border-radius:.25rem; font-size:.85rem; margin-bottom:.5rem;}
.rtl {direction: rtl; text-align: right;}
.product-card {border:1px solid #e5e7eb; border-radius:.5rem; padding:1rem; margin:.5rem 0;}
</style>
""", unsafe_allow_html=True)


st.title("3am Mom")
st.caption("Voice-first parenting copilot for Mumzworld customers. Type below or record audio in the Voice panel.")

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
        st.markdown(f'<span class="lang-chip">Detected: {resp.user_input_language} → {resp.response_language}</span>', unsafe_allow_html=True)
        if resp.escalation and resp.escalation.triggered:
            triggers = ", ".join(resp.escalation.triggers)
            st.markdown(f'<div class="escalation-banner"><b>⚠ Medical attention needed</b><br>{resp.escalation.advice}<br><small>NICE NG143 categories: {triggers}</small></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="{rtl_resp}">{resp.response_text}</div>', unsafe_allow_html=True)
        if resp.products_recommended:
            st.markdown("**Suggested products**")
            for r in resp.products_recommended:
                p = r.product
                with st.container():
                    st.markdown(f'<div class="product-card"><b>{p.name_en}</b> · AED {p.price_aed:.0f}<br><small>{p.description_en}</small><br><a href="#">View on Mumzworld</a></div>', unsafe_allow_html=True)
        st.caption(f"Response in {latency:.2f}s · confidence {resp.confidence:.2f}")


st.divider()
st.subheader("🎤 Voice mode")
st.caption("Tap to record, then tap stop. Audio is sent to Gemini 3.1 Flash Live preview. The same system prompt and tools as text mode.")

mic_audio = st.audio_input("Record your question")
if mic_audio is not None:
    wav_bytes = mic_audio.getvalue()
    with st.spinner("Transcribing + thinking + speaking..."):
        try:
            t0 = time.time()
            result = turn_voice(st.session_state.agent, wav_bytes)
            voice_latency = time.time() - t0
        except Exception as e:
            st.error(f"Voice error: {type(e).__name__}: {e}")
            result = None

    if result:
        if result.get("user_transcript"):
            st.markdown(f"**You said:** {result['user_transcript']}")
        if result.get("agent_transcript"):
            st.markdown(f"**Agent:** {result['agent_transcript']}")
        if result.get("audio_wav"):
            st.audio(result["audio_wav"], format="audio/wav", autoplay=True)
        if result.get("tool_log"):
            with st.expander("Tool calls used"):
                for t in result["tool_log"]:
                    st.caption(f"{t['name']}({t['args']})")
        st.caption(f"Voice round-trip: {voice_latency:.1f}s")

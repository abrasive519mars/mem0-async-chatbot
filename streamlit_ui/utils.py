import requests
import streamlit as st
from streamlit import session_state

def send_chat_request(endpoint: str, user_id: str, prompt: str, base_url: str):
    url = f"{base_url}/{endpoint}"
    try:
        resp = requests.post(
            url,
            json={"user_id": user_id, "user_input": prompt},
            timeout=60  # Increase timeout for LLM calls
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"response": f"Error: {e}", "fetch_time": None, "response_time": None}

def render_chat_tab(endpoint: str, history_key: str, base_url: str):
    result = None  # Ensure result is always defined
    if history_key not in session_state:
        session_state[history_key] = []

    # Display past messages
    for msg in session_state[history_key]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # Show timing for assistant messages if available
            if msg["role"] == "assistant" and "timing" in msg:
                fetch, resp = msg["timing"]
                st.caption(
                    f"🕒 Fetch: {fetch:.2f}s | Response: {resp:.2f}s"
                )
            # Show retrieved memories in a dropdown for assistant messages
            if msg["role"] == "assistant" and "memories" in msg and msg["memories"]:
                with st.expander("Show Retrieved Memories"):
                    for mem_type, mem_text in msg["memories"].items():
                        st.markdown(f"**{mem_type.capitalize()} Memories:**")
                        for line in mem_text.strip().split('\n'):
                            if line.strip():
                                st.markdown(f"- {line.strip()}")

    prompt = st.chat_input(
        "Type your message...", 
        key=f"chat_input_{history_key}"
    )
    if prompt:
        session_state[history_key].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get bot reply and timings
        result = send_chat_request(endpoint, session_state["user_id"], prompt, base_url)
        reply = result.get("response", "")
        fetch_time = result.get("fetch_time", None)
        response_time = result.get("response_time", None)
        memories = result.get("memories_retrieved") or result.get("memories", {})

        # Store and show assistant message with timing and memories
        msg_data = {
            "role": "assistant",
            "content": reply,
            "memories": memories
        }
        if fetch_time is not None and response_time is not None:
            msg_data["timing"] = (fetch_time, response_time)
        session_state[history_key].append(msg_data)

        with st.chat_message("assistant"):
            st.markdown(reply)
            if fetch_time is not None and response_time is not None:
                st.caption(
                    f"🕒 Fetch: {fetch_time:.2f}s | Response: {response_time:.2f}s"
                )
            if memories:
                with st.expander("Show Retrieved Memories"):
                    for mem_type, mem_text in memories.items():
                        st.markdown(f"**{mem_type.capitalize()} Memories:**")
                        for line in mem_text.strip().split('\n'):
                            if line.strip():
                                st.markdown(f"{line.strip()}")

    return result

def get_user_memories_from_redis(user_id: str):
    """
    Placeholder for Redis integration.
    When Redis is ready, fetch all memories for the user from Redis and return as a list of dicts.
    For now, returns None to show 'coming soon' in the UI.
    """
    # Example placeholder:
    # import redis, json
    # r = redis.Redis(host='localhost', port=6379, db=0)
    # memories = r.lrange(f"memories:{user_id}", 0, -1)
    # return [json.loads(m.decode()) for m in memories]
    return None

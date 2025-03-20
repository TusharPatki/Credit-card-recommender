import os

import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()#configure the environment variables

st.set_page_config(page_title="Credit Card Recommender", page_icon=":credit_card:", layout="wide")

google_api_key = os.getenv("GOOGLE_API_KEY")

if not google_api_key:
    st.error("Google API key not found. Please set the GOOGLE_API_KEY environment variable.")
    st.stop()
    
genai.configure(api_key=google_api_key)
model = genai.GenerativeModel("gemini-2.0-flash")

def translate_role_for_streamLit(user_role):
    if user_role == "model":
        return "assistant"
    else:
        return user_role
    
if "chat_session" not in st.session_state:
    st.session_state.chat_session = model.start_chat(history=[])

    
for message in st.session_state.chat_session.history:
    with st.chat_message(translate_role_for_streamLit(message.role)):
        st.markdown(message.parts[0].text)

user_prompt = st.chat_input("Enter your prompt here...")

if user_prompt:
    st.chat_message("user").markdown(user_prompt)
    
    gemini_response = st.session_state.chat_session.send_message(user_prompt)

    with st.chat_message("assistant"):
        st.markdown(gemini_response.text)
    
    
    
    
    





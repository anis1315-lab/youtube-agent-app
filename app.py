import streamlit as st
import os
import asyncio
from dotenv import load_dotenv
from pexels_api import API
import requests
import edge_tts
import nest_asyncio

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Apply the patch for asyncio
nest_asyncio.apply()

# --- 0. Load API Keys ---
load_dotenv()
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- 1. Agent Configuration ---
llm = ChatGroq(model_name="llama3-8b-8192", groq_api_key=GROQ_API_KEY)
output_parser = StrOutputParser()

idea_generation_prompt = ChatPromptTemplate.from_template("Brainstorm 5 viral video ideas about {topic}. Provide catchy titles.")
script_writing_prompt = ChatPromptTemplate.from_template("Write an energetic YouTube script for this title: {video_title}. Include a hook, main body, and call to action.")

idea_generation_chain = idea_generation_prompt | llm | output_parser
script_writing_chain = script_writing_prompt | llm | output_parser

# --- 2. Web App Interface ---
st.set_page_config(page_title="AI YouTube Agent", page_icon="🤖", layout="wide")
st.title("🤖 AI Agent for Faceless YouTube Channels")

col1, col2, col3 = st.columns(3)

# == COLUMN 1: IDEA GENERATION ==
with col1:
    st.subheader("Step 1: Generate Ideas")
    topic = st.text_input("Enter a broad topic:", key="topic_input")
    if st.button("Generate Ideas", key="generate_ideas_button"):
        if not GROQ_API_KEY:
            st.error("Groq API key not found. Please add it to your Streamlit secrets.")
        elif topic:
            with st.spinner("🧠 Brainstorming ideas..."):
                st.session_state.ideas = idea_generation_chain.invoke({"topic": topic})
            st.success("Ideas generated!")
        else:
            st.warning("Please enter a topic.")

# == COLUMN 2: SCRIPT & VOICEOVER ==
with col2:
    st.subheader("Step 2: Create Content")
    if 'ideas' in st.session_state:
        idea_list = [line for line in st.session_state.ideas.split('\n') if line.strip()]
        selected_idea = st.selectbox("Choose an idea:", options=idea_list, key="idea_select")
        
        if st.button("Create Script & Voiceover", key="create_content_button"):
            with st.spinner("✍️ Writing script..."):
                script = script_writing_chain.invoke({"video_title": selected_idea})
                st.session_state.script = script

            with st.spinner("🎙️ Creating voiceover..."):
                async def create_voiceover(text_to_speak):
                    VOICE = "en-US-GuyNeural"
                    communicate = edge_tts.Communicate(text_to_speak, VOICE, rate="+20%")
                    await communicate.save("voiceover.mp3")

                # Run the async function
                asyncio.run(create_voiceover(script))
                st.session_state.audio_ready = True
            st.success("Script & Voiceover complete!")

# == COLUMN 3: FIND VISUALS ==
with col3:
    st.subheader("Step 3: Find Visuals")
    if 'audio_ready' in st.session_state:
        keywords = st.text_input("Enter keywords from script:", key="keywords_input")
        if st.button("Find Videos", key="find_videos_button"):
            if not PEXELS_API_KEY:
                st.error("Pexels API key not found. Please add it to your Streamlit secrets.")
            elif keywords:
                with st.spinner("🖼️ Searching for videos on Pexels..."):
                    try:
                        api = API(PEXELS_API_KEY)
                        search_term = keywords.split(',')[0].strip()
                        api.search(search_term, page=1, results_per_page=5)
                        videos = api.get_entries()
                        st.session_state.videos = videos
                    except Exception as e:
                        st.error(f"An error occurred: {e}")
                st.success("Search complete!")

# --- Display Area for Results ---
st.write("---")
st.header("Generated Content")

if 'script' in st.session_state:
    with st.expander("View Generated Script and Voiceover"):
        st.write(st.session_state.script)
        if 'audio_ready' in st.session_state:
            st.audio("voiceover.mp3")
            with open("voiceover.mp3", "rb") as file:
                st.download_button("Download Voiceover (MP3)", file, "voiceover.mp3")

if 'videos' in st.session_state:
    with st.expander("View Found Visuals"):
        if st.session_state.videos:
            for video in st.session_state.videos:
                # CORRECTED LINE
                st.write(f"**Video by:** {video.photographer}")
                video_file_link = next((f.link for f in video.video_files if f.quality != 'streaming'), None)
                if video_file_link:
                    st.video(video_file_link)
                st.write("---")
        else:
            st.write("No videos found for that search term.")
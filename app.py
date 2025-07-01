import streamlit as st
import os
import asyncio
from dotenv import load_dotenv
import requests
import edge_tts
import nest_asyncio
import ffmpeg

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Apply the patch for asyncio
nest_asyncio.apply()

# --- 0. Load API Keys & Setup ---
load_dotenv()
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Create a directory to store downloaded videos
if not os.path.exists('videos'):
    os.makedirs('videos')

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
                asyncio.run(create_voiceover(script))
                st.session_state.audio_ready = True
            st.success("Script & Voiceover complete!")

# == COLUMN 3: FIND & ASSEMBLE VISUALS ==
with col3:
    st.subheader("Step 3 & 4: Get Visuals & Create Video")
    if 'audio_ready' in st.session_state:
        keywords = st.text_input("Enter keywords from script:", key="keywords_input")
        if st.button("1. Find & Download Videos", key="find_videos_button"):
            if not PEXELS_API_KEY:
                st.error("Pexels API key not found.")
            elif keywords:
                with st.spinner("🖼️ Searching and downloading videos..."):
                    try:
                        headers = {"Authorization": PEXELS_API_KEY}
                        query = keywords.split(',')[0].strip()
                        url = f"https://api.pexels.com/videos/search?query={query}&per_page=5"
                        response = requests.get(url, headers=headers)
                        response.raise_for_status()
                        videos_json = response.json().get('videos', [])
                        
                        st.session_state.video_paths = []
                        for i, video_data in enumerate(videos_json):
                            video_files = video_data.get('video_files', [])
                            video_link = next((f['link'] for f in video_files if f.get('width') == 1920), None) # Prefer 1080p
                            if not video_link:
                                video_link = video_files[0]['link'] # Fallback to first available

                            file_path = f"videos/video_{i}.mp4"
                            with open(file_path, "wb") as f:
                                f.write(requests.get(video_link).content)
                            st.session_state.video_paths.append(file_path)
                    except Exception as e:
                        st.error(f"An error occurred: {e}")
                st.success(f"{len(st.session_state.video_paths)} videos downloaded successfully!")

        if 'video_paths' in st.session_state and st.session_state.video_paths:
            if st.button("2. Assemble Final Video", key="assemble_video_button"):
                with st.spinner("🎬 Assembling the final video... This can take several minutes!"):
                    try:
                        audio_path = "voiceover.mp3"
                        video_paths = st.session_state.video_paths
                        output_path = "final_video.mp4"

                        # Probe the audio file to get its duration
                        probe = ffmpeg.probe(audio_path)
                        audio_duration = float(probe['format']['duration'])

                        # Create input streams for all video files
                        video_inputs = [ffmpeg.input(path) for path in video_paths]

                        # Concatenate all video streams (v=1 video, a=0 audio)
                        stitched_video = ffmpeg.concat(*video_inputs, v=1, a=0)

                        # Input the audio stream
                        audio_input = ffmpeg.input(audio_path)

                        # Combine video with audio, trim to audio duration, and set codecs
                        ffmpeg.output(stitched_video, audio_input, output_path, vcodec='libx264', acodec='aac', t=audio_duration).overwrite_output().run(quiet=True)
                        st.session_state.final_video_ready = True
                    except ffmpeg.Error as e:
                        st.error(f"FFmpeg Error: {e.stderr.decode('utf8')}")
                    except Exception as e:
                        st.error(f"An error occurred during video assembly: {e}")

# --- Display Area for Final Video ---
st.write("---")
st.header("Final Video")

if 'final_video_ready' in st.session_state:
    st.video("final_video.mp4")
    with open("final_video.mp4", "rb") as file:
        st.download_button("Download Final Video (MP4)", file, "final_video.mp4")
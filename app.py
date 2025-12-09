import streamlit as st
import os
from dotenv import load_dotenv
from utils import save_uploaded_file, read_file_content, recorder_factory
from ai_logic import configure_gemini, get_gemini_response, generate_final_feedback
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration

# Load environment variables
load_dotenv()

# --- Page Config ---
st.set_page_config(
    page_title="PrepMate-AI",
    page_icon="👔",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Session State ---
if "step" not in st.session_state:
    st.session_state.step = "setup"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "user_info" not in st.session_state:
    st.session_state.user_info = {}

# --- Main Logic ---

if st.session_state.step == "setup":
    st.title(":blue[PrepMate] : AI Mock Interview System")
    st.caption("Ace interviews with intelligent, personalized practice.")
    
    with st.container(border=False):
        st.subheader("Candidate Registration") 
        
        with st.form("registration_form"):
            # Row 1: Candidate Info (3 Columns)
            c1, c2, c3 = st.columns(3)
            with c1:
                name = st.text_input("Full Name", placeholder="e.g. Nilesh Bagul")
            with c2:
                role = st.text_input("Target Role", placeholder="e.g. Product Manager")
            with c3:
                experience = st.selectbox("Experience Level", ["Intern", "Junior", "Mid-Level", "Senior", "Executive"])
            

            c4, c5, c6 = st.columns(3)
            with c4:
                rubric = st.selectbox("Evaluation Rubric", 
                                    ["General Behavioral (STAR)", 
                                     "Technical Deep Dive", 
                                     "System Design & Architecture", 
                                     "Leadership & Culture"])
            with c5:
                # Mode selection moved here
                interaction_mode = st.radio("Interaction Mode", ["Text 💬", "Audio 🎤", "Video 📹"], horizontal=True)
            with c6:
                # Question Bank Uploader
                uploaded_q_bank = st.file_uploader(
                    "Optional: Question Bank (.txt, .pdf, .docx)", 
                    type=['txt', 'pdf', 'docx'], 
                    help="Provide a question bank file, and the AI will ask questions sequentially from it."
                )

            # Row 3: Skills + API Key Logic
            api_key = os.getenv("GEMINI_API_KEY")
            
            if not api_key:
                c7, c8 = st.columns([3, 1])
                with c7:
                    skills = st.text_area("Key Skills / Tech Stack", placeholder="e.g. Python, SQL, Agile...", height=100)
                with c8:
                    st.markdown("**System Access**")
                    api_key = st.text_input("Gemini API Key", type="password", help="Required")
            else:
                # If key EXISTS, show Skills full width (Hide System Access UI completely)
                skills = st.text_area("Key Skills / Tech Stack", placeholder="e.g. Python, SQL, Agile...", height=100)

            st.markdown("---")
            submit_btn = st.form_submit_button("🚀 Start Interview Session", type="primary", use_container_width=True)
            
            if submit_btn:
                if api_key:
                    # Process Question Bank
                    q_bank_text = None
                    if uploaded_q_bank is not None:
                        q_bank_text = read_file_content(uploaded_q_bank)
                        if q_bank_text is None:
                            st.stop() 
                    
                    st.session_state.user_info = {
                        "name": name, "role": role, "skills": skills, 
                        "level": experience, "mode": interaction_mode, 
                        "rubric": rubric, "api_key": api_key,
                        "question_bank": q_bank_text
                    }
                    
                    # Customize System Prompt
                    if q_bank_text:
                        sys_prompt = f"""
                        You are PrepMate, an expert AI Interviewer.
                        CONTEXT:
                        You have been provided with a specific Question Bank below. 
                        Candidate Name: {name}
                        Role: {role}

                        INSTRUCTIONS:
                        1. Start by welcoming the candidate briefly.
                        2. IMMEDIATELY ask the FIRST question from the Question Bank below.
                        3. Wait for the user's answer.
                        4. CRITICAL: Do NOT evaluate, correct, or give feedback on the answer. Even if the answer is completely wrong, simply accept it and move to the next question.
                        5. Ask questions ONE BY ONE. Do not group them.
                        6. When the list is finished, say "Thank you, the interview is complete."

                        QUESTION BANK:
                        {q_bank_text}
                        """
                    else:
                        sys_prompt = f"You are PrepMate, an AI Interviewer. Interviewing for {role}. Skills: {skills}. Rubric: {rubric}. Act human. Start with a greeting."
                    
                    st.session_state.chat_history = [{"role": "system", "content": sys_prompt}]
                    st.session_state.step = "interview"
                    st.rerun()
                else:
                    st.error("Please enter a valid API Key to proceed.")

elif st.session_state.step == "interview":
    user_info = st.session_state.user_info
    
    # Top Action Bar
    col_h1, col_h2 = st.columns([6, 1])
    with col_h1:
        st.subheader(f"💬 Interviewing: :blue[{user_info['name']}]")
        if user_info.get('question_bank'):
            st.caption("📄 **Custom Question Bank Mode Active**")
        else:
            st.caption(f"Evaluation Rubric: {user_info['rubric']}")
    with col_h2:
        if st.button("🏁 Finish", type="primary", use_container_width=True):
            st.session_state.step = "feedback"
            st.rerun()

    st.divider()

    model = configure_gemini(user_info['api_key'])

    if model:
        # Initialize
        if len(st.session_state.chat_history) == 1:
            with st.spinner("Interviewer is preparing..."):
                initial_msg = model.generate_content(st.session_state.chat_history[0]['content']).text
                st.session_state.chat_history.append({"role": "assistant", "content": initial_msg})

        # Chat History Container
        chat_container = st.container(height=400) # Fixed height for professional scroll
        with chat_container:
            for message in st.session_state.chat_history:
                if message["role"] != "system":
                    avatar = "👨‍💼" if message["role"] == "user" else "🤖"
                    with st.chat_message(message["role"], avatar=avatar):
                        if message.get("content"): st.markdown(message["content"])
                        if message.get("audio"): st.audio(message["audio"])
                        if message.get("video_file"): st.video(message["video_file"])

        # Input Area
        with st.container(border=True):
            st.markdown(f"**Your Response**")
            
            user_text = None
            user_audio = None
            video_file_path = None
            submit = False

            if "Text" in user_info['mode']:
                user_text = st.chat_input("Type your answer here...")
                if user_text: submit = True

            elif "Audio" in user_info['mode']:
                user_audio = st.audio_input("Record Answer")
                if user_audio:
                    if st.button("Submit Audio", type="primary"): 
                        submit = True

            elif "Video" in user_info['mode']:
                tab1, tab2 = st.tabs(["🔴 Live Camera", "📁 Upload Video"])
                with tab1:
                    output_video_file = "recorded_video.webm"
                    streamer = webrtc_streamer(
                        key="video-recorder", 
                        mode=WebRtcMode.SENDRECV,
                        rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
                        media_stream_constraints={"video": {"width": {"ideal": 1280}, "height": {"ideal": 720}}, "audio": True},
                        in_recorder_factory=recorder_factory
                    )
                    if os.path.exists(output_video_file) and not streamer.state.playing:
                        st.success("Video Captured.")
                        if st.button("Submit Recorded Video", type="primary"):
                            video_file_path = output_video_file
                            submit = True
                with tab2:
                    uploaded = st.file_uploader("Upload video", type=['mp4', 'mov', 'webm'], label_visibility="collapsed")
                    if uploaded and st.button("Submit Upload", type="secondary"):
                        video_file_path = save_uploaded_file(uploaded)
                        submit = True

        if submit:
            audio_path = None
            if user_audio: audio_path = save_uploaded_file(user_audio)
            
            with chat_container:
                with st.chat_message("user", avatar="👨‍💼"):
                    if user_text: st.markdown(user_text)
                    if user_audio: st.audio(user_audio)
                    if video_file_path: st.video(video_file_path)

            st.session_state.chat_history.append({
                "role": "user", "content": user_text, 
                "audio": user_audio, "video_file": video_file_path
            })

            with st.status("Analyzing response...", expanded=True) as status:
                ai_response = get_gemini_response(
                    model, st.session_state.chat_history, 
                    user_input=user_text, audio_path=audio_path, video_path=video_file_path
                )
                status.update(label="Response received", state="complete", expanded=False)
            
            if audio_path: os.remove(audio_path)
            
            st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
            st.rerun()

elif st.session_state.step == "feedback":
    st.title("📝 Interview Feedback Report")
    st.divider()
    
    model = configure_gemini(st.session_state.user_info['api_key'])
    if model:
        with st.spinner("Generating feedback..."):
            report = generate_final_feedback(model, st.session_state.chat_history, st.session_state.user_info)
        
        with st.container(border=True):
            st.markdown(report)
        
        st.write("")
        if st.button("🔄 Start New Session", type="primary"):
            st.session_state.step = "setup"
            st.session_state.chat_history = []
            st.rerun()
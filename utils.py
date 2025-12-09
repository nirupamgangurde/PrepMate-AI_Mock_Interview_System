import streamlit as st
import tempfile
import os

from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
from aiortc.contrib.media import MediaRecorder

def save_uploaded_file(uploaded_file):
    """Saves uploaded file to temp and returns path."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1] if '.' in uploaded_file.name else 'wav'}") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            return tmp_file.name
    except Exception as e:
        st.error(f"Error handling file: {e}")
        return None

def read_file_content(uploaded_file):
    """Reads content from TXT, PDF, or DOCX files."""
    try:
        if uploaded_file.type == "text/plain":
            return uploaded_file.read().decode("utf-8")
        
        elif uploaded_file.type == "application/pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(uploaded_file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                return text
            except ImportError:
                st.error("⚠️ PDF support requires 'pypdf'. Run: `pip install pypdf`")
                return None
        
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            try:
                import docx
                doc = docx.Document(uploaded_file)
                return "\n".join([para.text for para in doc.paragraphs])
            except ImportError:
                st.error("⚠️ Word support requires 'python-docx'. Run: `pip install python-docx`")
                return None
        else:
            return None
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return None

def recorder_factory():
    return MediaRecorder("recorded_video.webm")
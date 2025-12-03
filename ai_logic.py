import streamlit as st
import google.generativeai as genai
import time
import PIL.Image

def configure_gemini(api_key):
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-2.5-flash')
    except Exception as e:
        st.error(f"Error configuring API: {e}")
        return None

def get_gemini_response(model, history, user_input=None, image_path=None, audio_path=None, video_path=None):
    """Orchestrates multimodal input to Gemini."""
    prompt_parts = []
    
    # 1. ALWAYS retrieve the Persistent System Prompt (Context/Persona)
    system_prompt_content = ""
    if history and history[0]['role'] == 'system':
        system_prompt_content = history[0]['content']
    
    # 2. Add Dynamic Instructions based on the current state
    question_bank = st.session_state.user_info.get('question_bank', None)
    rubric = st.session_state.user_info.get('rubric', 'General')
    skills = st.session_state.user_info.get('skills', 'General')
    
    # Define the current task instruction
    current_task_instruction = f"""
    \n--- CURRENT INTERVIEW STATE ---
    1. Analyze the candidate's latest response.
    2. **CRITICAL:** If the candidate provided a VIDEO or AUDIO file, you MUST listen to the spoken content in the file to understand their answer. Do not ignore the audio track.
    3. The Video/Audio provided is the DIRECT ANSWER to the LAST question found in the "Conversation History" below.
    4. Keep your responses concise and conversational.
    """

    # CONDITIONAL LOGIC: QUESTION BANK VS DYNAMIC
    if question_bank:
        # Serial Questioning Mode WITH CORRECTION
        current_task_instruction += f"""
        5. **STRICT MODE ACTIVE:** You have been provided a 'Question Bank'. 
        6. **YOUR TASK:** a) Evaluate the candidate's answer to the previous question (Listen carefully if video/audio).
           b) **IMPORTANT:** Explicitly state the **IDEAL/CORRECT ANSWER** for that question so the candidate can learn. Label it "✅ Ideal Answer:".
           c) Then, find the NEXT unanswered question from the 'Question Bank' below (in serial order) and ask ONLY that.
        7. If all questions in the bank are finished, politely conclude the interview.
        
        --- QUESTION BANK START ---
        {question_bank}
        --- QUESTION BANK END ---
        """
    else:
        # Standard Dynamic Mode
        current_task_instruction += f"""
        5. Acknowledge the candidate's answer naturally.
        6. Do NOT provide explicit "feedback" or "scores" yet. Save that for the end.
        7. Ask the NEXT follow-up question based on the Rubric: "{rubric}".
        8. Focus on these skills: {skills}.
        """
    
    # Combine Persistent Persona + Current Task
    full_system_instruction = system_prompt_content + current_task_instruction
    prompt_parts.append(full_system_instruction)

    # 3. Add User Inputs (Multimodal) - These represent the CURRENT turn
    if user_input:
        prompt_parts.append(f"Candidate Answer (Text): {user_input}")
    
    if image_path:
        img = PIL.Image.open(image_path)
        prompt_parts.append("Candidate Visual Feed:")
        prompt_parts.append(img)
    
    if audio_path:
        audio_file = genai.upload_file(path=audio_path)
        prompt_parts.append("Candidate Audio Answer:")
        prompt_parts.append(audio_file)
    
    if video_path:
        video_file = genai.upload_file(path=video_path)
        # Waiting for processing
        while video_file.state.name == "PROCESSING":
            time.sleep(1)
            video_file = genai.get_file(video_file.name)
        
        # Check if processing failed
        if video_file.state.name == "FAILED":
            return "⚠️ Error: The AI could not process the video file. Please try recording again."
            
        prompt_parts.append("Candidate Video Answer (Please listen to the audio track carefully for the response):")
        prompt_parts.append(video_file)

    # 4. Add Conversation Context (HISTORY ONLY)
    conversation_context = "--- CONVERSATION HISTORY (Previous Turns) ---\n"
    messages_to_include = history[1:-1] if len(history) > 1 else []
    messages_to_include = messages_to_include[-6:] 
    
    for msg in messages_to_include:
        if msg['role'] != 'system':
            content_text = msg.get('content', '')
            if not content_text:
                if msg.get('video_file'): content_text = "[Video Answer]"
                elif msg.get('audio'): content_text = "[Audio Answer]"
            conversation_context += f"{msg['role'].upper()}: {content_text}\n"
    
    prompt_parts.append(conversation_context)
    prompt_parts.append("\nINTERVIEWER (You):")

    try:
        response = model.generate_content(prompt_parts)
        return response.text
    except Exception as e:
        return f"Error from AI: {str(e)}"

def generate_final_feedback(model, history, user_info):
    """Generates the final structured report."""
    conversation_text = ""
    for msg in history:
        role = "Interviewer" if msg['role'] in ['system', 'assistant'] else "Candidate"
        content = msg.get('content', '')
        if not content:
            if msg.get('video_file'): content = "[Video Answer]"
            elif msg.get('audio'): content = "[Audio Answer]"
        conversation_text += f"{role}: {content}\n\n"
        
    prompt = f"""
    The interview has concluded. Please generate a detailed Feedback Report.
    Candidate Name: {user_info['name']}
    Role: {user_info['role']}
    Target Skills: {user_info['skills']}
    Rubric Used: {user_info['rubric']}
    Conversation History:
    {conversation_text}
    -----------------------------
    Please provide the feedback in the following Markdown structure:
    ## 1. Executive Summary
    ## 2. Rubric Evaluation ({user_info['rubric']})
    ## 3. Skill Gap Analysis
    ## 4. Communication & Behavioral Score
    ## 5. Final Recommendation
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating feedback: {e}"
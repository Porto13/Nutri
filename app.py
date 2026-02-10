def get_gemini_response(prompt, image=None, json_mode=False):
    """Call Gemini API."""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: 
        return "ERROR_NO_KEY"
        
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        config = genai.GenerationConfig(response_mime_type="application/json") if json_mode else None
        
        parts = [prompt]
        if image:
            parts.insert(0, image)
            
        response = model.generate_content(parts, generation_config=config)
        return response.text
    except Exception as e:
        # RETURN THE ACTUAL ERROR SO WE CAN SEE IT
        return f"ERROR_DETAILS: {str(e)}"

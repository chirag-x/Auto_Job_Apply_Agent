import pypdf
import json

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extracts raw text from a PDF resume using pypdf.
    """
    text = ""
    try:
        with open(file_path, "rb") as file:
            reader = pypdf.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error extracting text from {file_path}: {e}")
    
    return text.strip()

def extract_text_from_bytes(file_bytes) -> str:
    """
    Extracts raw text from a PDF file uploaded in memory (e.g. via Streamlit).
    """
    text = ""
    try:
        reader = pypdf.PdfReader(file_bytes)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        print(f"Error extracting text from bytes: {e}")
    
    return text.strip()

def extract_structured_data(raw_text: str) -> dict:
    """
    Uses the LLM Gateway to extract structured data (skills, experience, education) 
    from the raw resume text.
    """
    from src.agent.llm_gateway import query_llm
    
    prompt = f"""
    You are an expert resume parser. Read the following resume text and extract the key information into a JSON object.
    You MUST return ONLY valid JSON and nothing else.
    
    Required JSON structure:
    {{
        "skills": ["skill1", "skill2"],
        "experience": [
            {{"company": "Company Name", "title": "Job Title", "duration": "Time there", "description": "Brief description"}}
        ],
        "education": [
            {{"institution": "University", "degree": "Degree", "year": "Year"}}
        ]
    }}
    
    Resume Text:
    {raw_text[:4000]} # Limit to roughly first 4000 characters to save tokens/context if needed
    """
    
    try:
        response = query_llm([{"role": "user", "content": prompt}], response_format={"type": "json_object"})
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"Failed to extract structured data with LLM: {e}")
        return {
            "skills": [],
            "experience": [],
            "education": [],
            "raw_length": len(raw_text),
            "error": str(e)
        }

def parse_resume_from_file(file_path: str) -> dict:
    """
    Parses a resume from a local file path.
    """
    raw_text = extract_text_from_pdf(file_path)
    structured_data = extract_structured_data(raw_text)
    
    return {
        "raw_text": raw_text,
        "structured_data": json.dumps(structured_data)
    }

def parse_resume_from_bytes(file_bytes) -> dict:
    """
    Parses a resume from an in-memory file object (used by Streamlit uploads).
    """
    raw_text = extract_text_from_bytes(file_bytes)
    structured_data = extract_structured_data(raw_text)
    
    return {
        "raw_text": raw_text,
        "structured_data": json.dumps(structured_data)
    }

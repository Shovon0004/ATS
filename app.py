from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import PyPDF2
import io
import requests
import json
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# Configuration
GEMINI_API_KEY = "AIzaSyAMTm-yRu49bFe5vb_OXoE9sI_HEHNCg0g"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF using PyPDF2"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text() + "\n"
        
        # Clean up the text
        text = text.strip()
        return text if text else None
        
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return None

def analyze_with_gemini(resume_text, mode="overall", job_description=""):
    """Analyze resume using Gemini AI"""
    
    if mode == "overall":
        prompt = f"""
        Analyze this resume for ATS (Applicant Tracking System) compatibility and overall quality. 
        Provide a realistic score between 30-95 based on:
        - Keyword usage and relevance
        - Formatting and structure
        - Content quality and completeness
        - ATS readability
        
        Resume text:
        {resume_text}
        
        Return your analysis in this exact JSON format:
        {{
            "ats_score": <number between 30-95>,
            "matched_keywords": [<array of keywords found in resume>],
            "missing_keywords": [<array of important keywords missing>],
            "suggestions": "<detailed suggestions for improvement>"
        }}
        """
    else:
        prompt = f"""
        Analyze this resume against the specific job description for ATS compatibility and job match.
        Provide a realistic score between 30-95 based on:
        - How well the resume matches the job requirements
        - Keyword alignment with job description
        - Relevant experience and skills
        - ATS readability
        
        Job Description:
        {job_description}
        
        Resume text:
        {resume_text}
        
        Return your analysis in this exact JSON format:
        {{
            "ats_score": <number between 30-95>,
            "matched_keywords": [<array of keywords from job description found in resume>],
            "missing_keywords": [<array of important job keywords missing from resume>],
            "suggestions": "<detailed suggestions for better job match>"
        }}
        """
    
    try:
        headers = {
            "Content-Type": "application/json"
        }
        
        data = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 1024,
            }
        }
        
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            text_response = result["candidates"][0]["content"]["parts"][0]["text"]
            
            # Extract JSON from response
            json_start = text_response.find('{')
            json_end = text_response.rfind('}') + 1
            json_str = text_response[json_start:json_end]
            
            return json.loads(json_str)
        else:
            print(f"Gemini API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Gemini analysis error: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze_resume():
    try:
        # Get form data
        mode = request.form.get('mode', 'overall')
        job_description = request.form.get('job_description', '')
        
        # Get uploaded file
        if 'resume' not in request.files:
            return jsonify({'error': 'No resume file uploaded'}), 400
        
        file = request.files['resume']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Extract text from PDF
        resume_text = extract_text_from_pdf(file)
        
        if not resume_text:
            return jsonify({'error': 'Could not extract text from PDF. Please ensure the PDF contains selectable text.'}), 400
        
        print(f"Extracted text length: {len(resume_text)}")
        print(f"Text preview: {resume_text[:200]}...")
        
        # Analyze with Gemini
        analysis = analyze_with_gemini(resume_text, mode, job_description)
        
        if not analysis:
            return jsonify({'error': 'Failed to analyze resume. Please try again.'}), 500
        
        return jsonify(analysis)
        
    except Exception as e:
        print(f"Analysis error: {e}")
        return jsonify({'error': 'An error occurred during analysis'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)

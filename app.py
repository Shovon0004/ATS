from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import PyPDF2
import io
import requests
import json
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")

class AIAnalysisError(Exception):
    """Raised when the AI provider cannot produce a usable analysis."""


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

def analyze_with_groq(resume_text, mode="overall", job_description=""):
    """Analyze resume using Groq's OpenAI-compatible API."""

    if not GROQ_API_KEY:
        raise AIAnalysisError("GROQ_API_KEY is not configured on the server.")
    
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
        
        Return only valid JSON in this exact format, with no Markdown or extra text:
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
        
        Return only valid JSON in this exact format, with no Markdown or extra text:
        {{
            "ats_score": <number between 30-95>,
            "matched_keywords": [<array of keywords from job description found in resume>],
            "missing_keywords": [<array of important job keywords missing from resume>],
            "suggestions": "<detailed suggestions for better job match>"
        }}
        """
    
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": "You are an ATS resume analyst. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_completion_tokens": 4096,
            "reasoning_effort": "low"
        }
        response = requests.post(GROQ_API_URL, headers=headers, json=data, timeout=30)
        if response.status_code != 200:
            print(f"Groq API error: {response.status_code} - {response.text[:1000]}")
            try:
                error_detail = response.json().get("error", {}).get("message", "")
            except ValueError:
                error_detail = ""
            detail_suffix = f" {error_detail}" if error_detail else ""
            raise AIAnalysisError(
                f"Groq API request failed ({response.status_code}) for model "
                f"{GROQ_MODEL}.{detail_suffix}"
            )

        try:
            result = response.json()
        except ValueError as error:
            raise AIAnalysisError("Groq returned an invalid API response.") from error

        choices = result.get("choices", [])
        if not choices:
            print(f"Groq returned no choices: {result}")
            raise AIAnalysisError("Groq returned no analysis choices.")

        text_response = (choices[0].get("message", {}).get("content") or "").strip()
        finish_reason = choices[0].get("finish_reason", "unknown")
        if not text_response:
            message = choices[0].get("message", {})
            print(f"Groq returned no content: finish_reason={finish_reason}, message={message}")
            raise AIAnalysisError(
                f"Groq returned an empty response (finish reason: {finish_reason})."
            )

        decoder = json.JSONDecoder()
        for json_start, character in enumerate(text_response):
            if character != '{':
                continue
            try:
                analysis, _ = decoder.raw_decode(text_response[json_start:])
                required_fields = {"ats_score", "matched_keywords", "missing_keywords", "suggestions"}
                if required_fields.issubset(analysis):
                    return analysis
                raise AIAnalysisError("Groq analysis was missing required fields.")
            except json.JSONDecodeError:
                continue

        print(f"Groq returned invalid JSON (finish reason: {finish_reason}): {text_response[:1000]}")
        raise AIAnalysisError(f"Groq returned invalid JSON (finish reason: {finish_reason}).")
    except AIAnalysisError:
        raise
    except requests.RequestException as error:
        print(f"Groq request error: {error}")
        raise AIAnalysisError("Could not connect to the Groq API.") from error
    except Exception as error:
        print(f"Groq analysis error: {error}")
        raise AIAnalysisError("Unexpected Groq analysis error.") from error

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
        
        # Analyze with Groq
        analysis = analyze_with_groq(resume_text, mode, job_description)
        
        return jsonify(analysis)
        
    except AIAnalysisError as e:
        return jsonify({'error': str(e)}), 502
    except Exception as e:
        app.logger.exception("Analysis error")
        return jsonify({'error': f'Analysis failed: {e}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)

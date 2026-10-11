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

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

class GeminiAnalysisError(Exception):
    """Raised when Gemini cannot produce a usable analysis."""


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

    if not GEMINI_API_KEY:
        raise GeminiAnalysisError("GEMINI_API_KEY is not configured on the server.")
    
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
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "ats_score": {"type": "INTEGER"},
                        "matched_keywords": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"}
                        },
                        "missing_keywords": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"}
                        },
                        "suggestions": {"type": "STRING"}
                    },
                    "required": [
                        "ats_score",
                        "matched_keywords",
                        "missing_keywords",
                        "suggestions"
                    ]
                }
            }
        }
        
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"Gemini API error: {response.status_code} - {response.text[:1000]}")
            raise GeminiAnalysisError(
                f"Gemini API request failed ({response.status_code}). Check the API key and model configuration."
            )

        try:
            result = response.json()
        except ValueError as error:
            raise GeminiAnalysisError("Gemini returned an invalid API response.") from error

        candidates = result.get("candidates", [])
        if not candidates:
            print(f"Gemini returned no candidates: {result}")
            raise GeminiAnalysisError("Gemini returned no analysis candidates.")

        parts = candidates[0].get("content", {}).get("parts", [])
        text_response = "".join(part.get("text", "") for part in parts).strip()
        if not text_response:
            print(f"Gemini returned an empty response: {result}")
            raise GeminiAnalysisError("Gemini returned an empty response.")

        # Parse the first complete JSON object, allowing Markdown fences or trailing text.
        decoder = json.JSONDecoder()
        for json_start, character in enumerate(text_response):
            if character != '{':
                continue
            try:
                analysis, _ = decoder.raw_decode(text_response[json_start:])
                required_fields = {
                    "ats_score",
                    "matched_keywords",
                    "missing_keywords",
                    "suggestions"
                }
                if required_fields.issubset(analysis):
                    return analysis
                print(f"Gemini analysis is missing fields: {analysis}")
                raise GeminiAnalysisError("Gemini analysis was missing required fields.")
            except json.JSONDecodeError:
                continue

        finish_reason = candidates[0].get("finishReason", "unknown")
        print(
            f"Gemini returned non-JSON analysis (finish reason: {finish_reason}): "
            f"{text_response[:1000]}"
        )
        raise GeminiAnalysisError(
            f"Gemini returned invalid JSON (finish reason: {finish_reason})."
        )
            
    except GeminiAnalysisError:
        raise
    except requests.RequestException as e:
        print(f"Gemini request error: {e}")
        raise GeminiAnalysisError("Could not connect to the Gemini API.") from e
    except Exception as e:
        print(f"Gemini analysis error: {e}")
        raise GeminiAnalysisError("Unexpected Gemini analysis error.") from e

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
        
        return jsonify(analysis)
        
    except GeminiAnalysisError as e:
        return jsonify({'error': str(e)}), 502
    except Exception as e:
        app.logger.exception("Analysis error")
        return jsonify({'error': f'Analysis failed: {e}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)

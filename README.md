# ATS Resume Checker - Flask Version

A professional ATS (Applicant Tracking System) resume checker built with Flask and powered by Google's Gemini AI.

## Features

- **Two Analysis Modes:**
  - Overall ATS Check: General resume optimization
  - Job-Specific Check: Targeted analysis against job descriptions

- **Real PDF Text Extraction:** Uses PyPDF2 for reliable text extraction
- **AI-Powered Analysis:** Google Gemini AI provides accurate scoring and suggestions
- **Professional UI:** Clean, responsive design similar to Enhancv

## Setup

1. Install dependencies:
\`\`\`bash
pip install -r requirements.txt
\`\`\`

2. Set your Gemini API key in the environment:
\`\`\`bash
export GEMINI_API_KEY="your-gemini-api-key"
\`\`\`

On Windows PowerShell, use `\$env:GEMINI_API_KEY="your-gemini-api-key"` instead.

3. Run the application:
\`\`\`bash
python app.py
\`\`\`

4. Open http://localhost:5000 in your browser

## How it Works

1. Upload your resume (PDF format)
2. Choose analysis mode (Overall or Job-Specific)
3. Get real-time analysis with:
   - ATS compatibility score (30-95 range)
   - Matched keywords from your resume
   - Missing important keywords
   - Detailed improvement suggestions

## Technical Details

- **Backend:** Flask with PyPDF2 for reliable PDF text extraction
- **AI:** Google Gemini 2.5 Flash for intelligent resume analysis
- **Frontend:** HTML/CSS/JavaScript with Tailwind CSS
- **No dummy data:** All scores and suggestions come directly from AI analysis

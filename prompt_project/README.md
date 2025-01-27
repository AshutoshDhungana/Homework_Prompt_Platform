# Homework Platform

A web platform for teachers to assign homework and track students' AI-assisted work.

## Features

- User roles (Teachers and Students)
- Assignment creation and management
- Student submission system
- AI assistance tracking
- Submission comparison with AI chat history

## Setup

1. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on `.env.example` and set your configuration:
- Set up your PostgreSQL database URL
- Generate a secure secret key
- Add your Google Gemini API key

4. Initialize the database:
```bash
# Connect to PostgreSQL and create the database
createdb homework_platform

# The tables will be automatically created when you run the application
```

5. Run the application:
```bash
python app.py
```

## Usage

1. Register as either a teacher or student
2. Teachers can:
   - Create assignments with title, instructions, and deadline
   - View student submissions and their AI interaction history
3. Students can:
   - View assigned homework
   - Get AI assistance while working
   - Submit their work

## Development

The application uses:
- Flask for the backend
- PostgreSQL for the database
- Google Gemini for AI assistance
- Bootstrap for the frontend

## Database Schema

The platform uses the following tables:
- users: Store user information and roles
- homework: Store assignment details
- studenthomework: Track student assignment status
- submissions: Store student submissions
- aiinteractions: Log AI assistance interactions
- teacherreview: Store teacher reviews and AI analysis 
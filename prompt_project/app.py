from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv
import sys
from sqlalchemy import text, Enum
import enum
from chatbot import Chatbot

# Load environment variables and add error handling
load_dotenv()

# Define valid roles
class UserRole(enum.Enum):
    teacher = "teacher"
    student = "student"

def check_environment_variables():
    required_vars = ['DATABASE_URL', 'SECRET_KEY', 'GOOGLE_API_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print("Error: Missing required environment variables:", missing_vars)
        print("Please check your .env file and ensure all required variables are set.")
        sys.exit(1)

def init_db(app):
    try:
        db = SQLAlchemy(app)
        with app.app_context():
            db.create_all()
        return db
    except Exception as e:
        print(f"Database initialization error: {str(e)}")
        print("Please check your database configuration and ensure PostgreSQL is running.")
        sys.exit(1)

# Check environment variables before proceeding
check_environment_variables()

app = Flask(__name__)

# Debug: Print configuration
print("Debug: DATABASE_URL =", os.getenv('DATABASE_URL'))

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database with error handling
db = init_db(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize Gemini API with error handling
try:
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    genai.configure(api_key=GOOGLE_API_KEY)
    
    # List available models and verify
    available_models = [m.name for m in genai.list_models() 
                       if 'generateContent' in m.supported_generation_methods]
    print("Available Gemini models:", available_models)
    
    # Initialize the model
    model = genai.GenerativeModel('gemini-pro')
    chat = model.start_chat(history=[])
    print("Gemini API connection successful!")
except Exception as e:
    print(f"Gemini API initialization error: {str(e)}")

# Initialize chatbot
chatbot = Chatbot()

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    db.session.rollback()
    print(f"Unhandled exception: {str(e)}")
    return jsonify({'error': 'An unexpected error occurred'}), 500

# Database connection test route
@app.route('/health')
def health_check():
    try:
        # Test database connection using text()
        db.session.execute(text('SELECT 1'))
        return jsonify({'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'database': str(e)}), 500

# Models
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    userid = db.Column('userid', db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    passwordhash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False)
    createdat = db.Column(db.DateTime, default=datetime.utcnow)

    def get_id(self):
        return str(self.userid)

class Homework(db.Model):
    __tablename__ = 'homework'
    homeworkid = db.Column('homeworkid', db.Integer, primary_key=True)
    teacherid = db.Column(db.Integer, db.ForeignKey('users.userid'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    duedate = db.Column(db.Date, nullable=False)
    createdat = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Add relationships
    teacher = db.relationship('User', backref='homework_assigned')
    student_homework = db.relationship('StudentHomework', backref='homework', lazy='dynamic')

class StudentHomework(db.Model):
    __tablename__ = 'studenthomework'
    studenthomeworkid = db.Column('studenthomeworkid', db.Integer, primary_key=True)
    homeworkid = db.Column(db.Integer, db.ForeignKey('homework.homeworkid'), nullable=False)
    studentid = db.Column(db.Integer, db.ForeignKey('users.userid'), nullable=False)
    status = db.Column(db.String(10), default='Pending')
    submissiondate = db.Column(db.DateTime)
    grade = db.Column(db.String(10))
    teachercomments = db.Column(db.Text)
    
    # Add relationships
    student = db.relationship('User', backref='homework_received')
    submissions = db.relationship('Submission', backref='student_homework', lazy='dynamic')
    ai_interactions = db.relationship('AIInteractions', backref='student_homework', lazy='dynamic')

class AIInteractions(db.Model):
    __tablename__ = 'aiinteractions'
    interactionid = db.Column('interactionid', db.Integer, primary_key=True)
    studenthomeworkid = db.Column(db.Integer, db.ForeignKey('studenthomework.studenthomeworkid'), nullable=False)
    interactiontext = db.Column(db.Text, nullable=False)
    airesponsetext = db.Column(db.Text, nullable=False)
    interactiontimestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Submission(db.Model):
    __tablename__ = 'submissions'
    submissionid = db.Column('submissionid', db.Integer, primary_key=True)
    studenthomeworkid = db.Column(db.Integer, db.ForeignKey('studenthomework.studenthomeworkid'), nullable=False)
    submissioncontent = db.Column(db.Text)
    submissionfilepath = db.Column(db.String(255))
    submissiontimestamp = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.json
        # Validate role
        if data['role'] not in ['teacher', 'student']:
            return jsonify({'error': 'Invalid role. Must be either "teacher" or "student"'}), 400
        
        # Check if email already exists
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already registered'}), 400

        user = User(
            name=data['name'],
            email=data['email'],
            passwordhash=generate_password_hash(data['password']),
            role=UserRole[data['role']]  # Convert string to enum
        )
        db.session.add(user)
        db.session.commit()
        return jsonify({'message': 'User registered successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Registration error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    if user and check_password_hash(user.passwordhash, data['password']):
        login_user(user)
        return jsonify({
            'message': 'Logged in successfully',
            'redirect': url_for('dashboard')
        })
    return jsonify({'message': 'Invalid credentials'}), 401

@app.route('/assignments', methods=['GET', 'POST'])
@login_required
def assignments():
    if request.method == 'POST' and current_user.role.value == 'teacher':
        try:
            data = request.json
            # Create the homework assignment
            homework = Homework(
                teacherid=current_user.userid,
                title=data['title'],
                description=data['description'],
                duedate=datetime.strptime(data['duedate'], '%Y-%m-%d').date()
            )
            db.session.add(homework)
            db.session.flush()  # This gets us the homework ID
            
            # Assign to all students
            students = User.query.filter_by(role=UserRole.student).all()
            for student in students:
                student_homework = StudentHomework(
                    homeworkid=homework.homeworkid,
                    studentid=student.userid,
                    status='Pending'
                )
                db.session.add(student_homework)
            
            db.session.commit()
            return jsonify({'message': 'Assignment created successfully'})
        except Exception as e:
            db.session.rollback()
            print(f"Failed to create assignment: {str(e)}")
            return jsonify({'error': 'Failed to create assignment'}), 500
    
    try:
        if current_user.role.value == 'teacher':
            # Teachers see all assignments they've created
            assignments = Homework.query.filter_by(teacherid=current_user.userid).all()
            return jsonify([{
                'id': a.homeworkid,
                'title': a.title,
                'description': a.description,
                'duedate': a.duedate.strftime('%Y-%m-%d')
            } for a in assignments])
        else:
            # Students see assignments with their submission status
            student_homework = StudentHomework.query.filter_by(studentid=current_user.userid).all()
            return jsonify([{
                'id': sh.homework.homeworkid,
                'title': sh.homework.title,
                'description': sh.homework.description,
                'duedate': sh.homework.duedate.strftime('%Y-%m-%d'),
                'status': sh.status,
                'submission_date': sh.submissiondate.strftime('%Y-%m-%d %H:%M:%S') if sh.submissiondate else None
            } for sh in student_homework])
    except Exception as e:
        print(f"Failed to fetch assignments: {str(e)}")
        return jsonify({'error': 'Failed to fetch assignments'}), 500

@app.route('/ai-help', methods=['POST'])
@login_required
def ai_help():
    try:
        data = request.json
        
        # Get AI response using chatbot
        response_text = chatbot.get_response(data['query'])
        
        if not response_text:
            raise Exception("Empty response from AI")
        
        # Store interaction in database
        interaction = AIInteractions(
            studenthomeworkid=data['studenthomeworkid'],
            interactiontext=data['query'],
            airesponsetext=response_text
        )
        db.session.add(interaction)
        db.session.commit()
        
        return jsonify({
            'response': response_text,
            'success': True
        })
    except Exception as e:
        db.session.rollback()
        print(f"AI help error: {str(e)}")
        return jsonify({
            'error': 'Failed to get AI assistance. Please try again.',
            'details': str(e)
        }), 500

@app.route('/submit', methods=['POST'])
@login_required
def submit_homework():
    data = request.json
    submission = Submission(
        studenthomeworkid=data['studenthomeworkid'],
        submissioncontent=data.get('content'),
        submissionfilepath=data.get('filepath')
    )
    db.session.add(submission)
    
    student_homework = StudentHomework.query.get(data['studenthomeworkid'])
    student_homework.status = 'Submitted'
    student_homework.submissiondate = datetime.utcnow()
    
    db.session.commit()
    return jsonify({'message': 'Homework submitted successfully'})

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/submissions/<int:homework_id>', methods=['GET'])
@login_required
def get_submissions(homework_id):
    if current_user.role.value != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 403
        
    try:
        # Get all submissions for this homework
        homework = Homework.query.get_or_404(homework_id)
        
        # Verify the teacher owns this homework
        if homework.teacherid != current_user.userid:
            return jsonify({'error': 'Unauthorized'}), 403
            
        submissions_data = []
        for student_hw in homework.student_homework:
            # Get the latest submission
            latest_submission = student_hw.submissions.order_by(Submission.submissiontimestamp.desc()).first()
            
            # Get AI interactions
            ai_interactions = [{
                'query': ai.interactiontext,
                'response': ai.airesponsetext,
                'timestamp': ai.interactiontimestamp.strftime('%Y-%m-%d %H:%M:%S')
            } for ai in student_hw.ai_interactions]
            
            submission_info = {
                'student_name': student_hw.student.name,
                'status': student_hw.status,
                'submission_date': student_hw.submissiondate.strftime('%Y-%m-%d %H:%M:%S') if student_hw.submissiondate else None,
                'content': latest_submission.submissioncontent if latest_submission else None,
                'ai_interactions': ai_interactions
            }
            submissions_data.append(submission_info)
            
        return jsonify(submissions_data)
    except Exception as e:
        print(f"Error fetching submissions: {str(e)}")
        return jsonify({'error': 'Failed to fetch submissions'}), 500

@app.route('/student-submission/<int:homework_id>', methods=['GET'])
@login_required
def get_student_submission(homework_id):
    try:
        # Get the student's homework assignment
        student_homework = StudentHomework.query.filter_by(
            homeworkid=homework_id,
            studentid=current_user.userid
        ).first_or_404()
        
        # Get the latest submission
        latest_submission = student_homework.submissions.order_by(
            Submission.submissiontimestamp.desc()
        ).first()
        
        # Get AI interactions
        ai_interactions = [{
            'query': ai.interactiontext,
            'response': ai.airesponsetext,
            'timestamp': ai.interactiontimestamp.strftime('%Y-%m-%d %H:%M:%S')
        } for ai in student_homework.ai_interactions]
        
        return jsonify({
            'submission': {
                'content': latest_submission.submissioncontent,
                'date': latest_submission.submissiontimestamp.strftime('%Y-%m-%d %H:%M:%S')
            } if latest_submission else None,
            'status': student_homework.status,
            'ai_interactions': ai_interactions
        })
    except Exception as e:
        print(f"Error fetching student submission: {str(e)}")
        return jsonify({'error': 'Failed to fetch submission'}), 500

if __name__ == '__main__':
    try:
        with app.app_context():
            # Test database connection before starting using text()
            db.session.execute(text('SELECT 1'))
            print("Database connection successful!")
            db.create_all()
        app.run(debug=True)
    except Exception as e:
        print(f"Failed to start application: {str(e)}")
        sys.exit(1) 
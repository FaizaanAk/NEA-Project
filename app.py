from flask import Flask, render_template, request, redirect, url_for, flash, session, get_flashed_messages, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import random  
import os
from notes import get_notes_content
from flashcards import get_flashcards_content
from quiz_ai import QuizGenerator, generate_quiz
from answer_checker_ai import AnswerCheckerAI
from functools import wraps

app = Flask(__name__, 
            static_url_path='/static',
            static_folder='static')
app.secret_key = 'your_secret_key'

answer_checker = AnswerCheckerAI()
notes_content = get_notes_content()
flashcards_by_year = get_flashcards_content()

#Admin authentication decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please login first.', 'error')
            return redirect(url_for('login'))
        
        conn = sqlite3.connect('user_database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
        user = cursor.fetchone()
        conn.close()
        
        if not user or not user[0]:
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

#Database initialisation
def initialise_user_database():
    conn = sqlite3.connect('user_database.db', check_same_thread=False)
    cursor = conn.cursor()

    # First create the users table if it doesn't exist
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL,
                        password TEXT NOT NULL)''')
    
    # Check if is_admin column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # Add is_admin column if it doesn't exist
    if 'is_admin' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0')
        conn.commit()

    #Courses Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_name TEXT NOT NULL,
        description TEXT
    )''')

    #Saved courses Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS saved_courses (
    user_id INTEGER,
    course_id INTEGER,
    PRIMARY KEY (user_id, course_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (course_id) REFERENCES courses(id))''')

    #Progress Tracking Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS course_progress (
        user_id INTEGER,
        course_id INTEGER,
        progress INTEGER DEFAULT 0,
        last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, course_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (course_id) REFERENCES courses(id)
    )''')

    #Quiz Questions Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS quiz_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER,
        topic_id INTEGER,
        subtopic TEXT,
        question TEXT,
        correct_answer TEXT,
        FOREIGN KEY (course_id) REFERENCES courses(id)
    )''')
    
    # Quiz Scores Table to track performance by subtopic
    cursor.execute('''CREATE TABLE IF NOT EXISTS quiz_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        topic_id INTEGER,
        subtopic TEXT,
        score INTEGER,
        total_questions INTEGER,
        percentage REAL,
        date_taken TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    conn.commit()
    try:
        # Execute the DELETE statement to remove invalid course_id rows
        cursor.execute('DELETE FROM saved_courses WHERE course_id IS NULL OR course_id = ""')
        conn.commit() 
        print("Invalid entries removed successfully.")
    
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    
    finally:
        conn.close()  # Close the database connection

#Route for the home page
@app.route('/')
def index():
    return render_template('index.html', title="StudyCore")

#Registering page
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        conn = sqlite3.connect('user_database.db')
        cursor = conn.cursor()

        #Checks if the user has entered a username and password
        if not username or not password:
            flash("Please enter a username and password.", "error")
            return redirect(url_for('register'))
        
        #Makes sure the username is greater than 5 letters to create a secure username
        if len(username) < 5:
            flash('Username must be at least 5 characters long', "error")
            return redirect(url_for('register'))
        
        #Makes sure the password is greater than 8 letters to create a secure password
        if len(password) < 8:
            flash('Password must be at least 8 characters long', "error")
            return redirect(url_for('register'))

        #Check if the username is already taken
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            flash('Username taken, please choose a different one.', "error")
            return redirect(url_for('register'))
        
        #Add user to the database
        cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
        conn.commit()
        conn.close()
        flash('Registration successful! Please login with your new account.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

#Handles the login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        conn = sqlite3.connect('user_database.db')
        cursor = conn.cursor()

        if not username or not password:
            flash("Please enter your username and password.")
            return redirect(url_for('login'))
        
        #Checks if the username is in the database
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        if not user:
            flash('Username not found. Would you like to register an account?')
            return redirect(url_for('login'))
        
        #Checks if the password matches the username 
        if user[2] == password:
            session['username'] = username
            session['user_id'] = user[0] 
            return redirect(url_for('dashboard'))
        else:
            flash('Wrong username or password')
            return redirect(url_for('login'))
    return render_template('login.html')

#Handles the dashboard page
@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html', hide_nav=True, title="StudyCore Dashboard")
    else:
        flash('You need to login first')
        return redirect(url_for('login'))
    
#Handles logging out
@app.route('/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    return redirect(url_for('index'))

#Handles the add course page
@app.route('/add_course')
def add_course():
    if 'username' not in session:
        flash('You need to login first to add courses!', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = sqlite3.connect('user_database.db', check_same_thread=False)
    cursor = conn.cursor()

    previous_url = url_for('dashboard')

    # Define pre-defined courses
    pre_defined_courses = [
        {"id": 1, "course_name": "Maths", "description": "Explore the world of numbers and problem-solving."},
        {"id": 2, "course_name": "Economics", "description": "Learn about economic principles and decision-making."},
        {"id": 3, "course_name": "Computer Science", "description": "Dive into the world of programming and technology."},
    ]

    saved_courses = []  

    try:
        # Retrieve user's saved course IDs
        cursor.execute('SELECT course_id FROM saved_courses WHERE user_id = ?', (user_id,))
        saved_course_ids = [row[0] for row in cursor.fetchall()]

        # Filter out saved courses from available courses
        available_courses = [course for course in pre_defined_courses if course['id'] not in saved_course_ids]

        # Retrieve saved courses details
        if saved_course_ids:
            query = 'SELECT id, course_name, description FROM courses WHERE id IN ({})'.format(', '.join(['?'] * len(saved_course_ids)))
            cursor.execute(query, saved_course_ids)
            saved_courses = cursor.fetchall()

    except Exception as e:
        # Handle database errors
        flash(f'An error occurred: {e}', 'danger')
        return redirect(url_for('dashboard'))   

    finally:
        conn.close()

    #Render the template with both available and saved courses
    return render_template('add_course.html', hide_nav=True, previous_url=previous_url, available_courses=available_courses, saved_courses=saved_courses)

#Handles the user saving courses
@app.route('/save_course', methods=['POST'])
def save_course():
    if 'username' not in session:
        flash('You need to login first to save courses!', 'danger')
        return redirect(url_for('login'))
    
    course_id = request.form.get('course_id')

    if not course_id:
        flash('Invalid course selected!', 'danger')
        return redirect(url_for('add_course'))
    
    user_id = session['user_id']

    conn = sqlite3.connect('user_database.db', check_same_thread=False)
    cursor = conn.cursor()

    try:
        # Check if the course is already saved
        cursor.execute('SELECT 1 FROM saved_courses WHERE user_id = ? AND course_id = ?', (user_id, course_id))
        if cursor.fetchone():
            flash('Course already saved!', 'warning')
        else:
            cursor.execute('INSERT INTO saved_courses (user_id, course_id) VALUES (?, ?)', (user_id, course_id))
            conn.commit()
            flash('Course saved successfully!', 'success')
    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')
        conn.rollback() 
    finally:
        conn.close()
    
    return redirect(url_for('add_course'))

#Handles the removal of courses
@app.route('/remove_course', methods=['POST'])
def remove_course():
    if 'username' not in session:
        flash('You need to login first!', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    course_id = request.form.get('course_id')

    if not course_id:
        flash('Invalid course selection.', 'danger')
        return redirect(url_for('add_course'))

    conn = sqlite3.connect('user_database.db', check_same_thread=False)
    cursor = conn.cursor()

    try:
        # Remove the course from saved_courses
        cursor.execute('DELETE FROM saved_courses WHERE user_id = ? AND course_id = ?', 
                      (user_id, course_id))
        conn.commit()
        flash('Course removed successfully!', 'success')

    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')

    finally:
        conn.close()

    return redirect(url_for('add_course'))

#Handles the select course page
@app.route('/select_course')
def select_course():
    if 'username' not in session:
        flash('You need to login first')
        return redirect(url_for('login'))
    
    previous_url = url_for('dashboard')

    user_id = session['user_id']
    conn = sqlite3.connect('user_database.db', check_same_thread=False)
    cursor = conn.cursor()
 
    try:
        # Retrieve user's saved courses
        cursor.execute('''
            SELECT c.id, c.course_name, c.description 
            FROM saved_courses sc 
            JOIN courses c ON sc.course_id = c.id 
            WHERE sc.user_id = ?
        ''', (user_id,))
        saved_courses = cursor.fetchall()

        return render_template('select_course.html', hide_nav=True, saved_courses=saved_courses, previous_url=previous_url)

    except Exception as e:
        flash(f'An error occurred: {e}')
        return redirect(url_for('dashboard'))

    finally:
        conn.close()

#Handles the view course page           
@app.route('/view_course/<int:course_id>')
def view_course(course_id):
    if 'username' not in session:
        flash('You need to login first!')
        return redirect(url_for('login'))

    conn = sqlite3.connect('user_database.db', check_same_thread=False)
    cursor = conn.cursor()

    try:
        # Retrieve course information
        cursor.execute('SELECT * FROM courses WHERE id = ?', (course_id,))
        course = cursor.fetchone()

        if not course:
            flash('Course not found.')
            return redirect(url_for('select_course'))

        user_id = session['user_id']
        
        # Calculate topic completion data based on course
        topics_completion = {}
        total_subtopics = 0
        completed_strong = 0
        
        # Define topic ranges for each course
        topic_ranges = {
            1: (1, 39),    # Maths topics
            2: (40, 79),   # Economics topics
            3: (80, 119)   # Computer Science topics
        }
        
        if course_id in topic_ranges:
            start_id, end_id = topic_ranges[course_id]
            
            # Get completion data for each topic
            for topic_id in range(start_id, end_id + 1):
                if topic_id in topic_data:
                    topic_subtopics = len(topic_data[topic_id]['subtopics'])
                    total_subtopics += topic_subtopics
                    
                    # Get completed subtopics for this topic
                    cursor.execute('''
                        SELECT COUNT(DISTINCT subtopic) 
                        FROM quiz_scores 
                        WHERE user_id = ? 
                        AND topic_id = ?
                        AND percentage >= 80
                    ''', (user_id, topic_id))
                    topic_completed = cursor.fetchone()[0]
                    
                    topics_completion[topic_id] = {
                        'total': topic_subtopics,
                        'completed': topic_completed
                    }
                    completed_strong += topic_completed
        
        # Calculate overall progress percentage
        progress = (completed_strong / total_subtopics * 100) if total_subtopics > 0 else 0

        previous_url = url_for('dashboard')

        return render_template('view_course.html', 
                             hide_nav=True, 
                             course=course, 
                             progress=progress,
                             topics_completion=topics_completion,
                             previous_url=previous_url,
                             title="StudyCore")

    except Exception as e:
        flash(f'An error occurred: {e}')
        return redirect(url_for('select_course'))

    finally:
        conn.close()

def setup_static_dirs():
    # Create static directories if they don't exist
    static_dirs = [
        'static/images',
    ]
    for directory in static_dirs:
        os.makedirs(directory, exist_ok=True)

topic_data = {
    # Maths Topics (Topic 1-39)
    1: {
        'name': 'Yet to be added',
        'subtopics': [
            'Yet to be added',
        ]
    },
    # Economics Topics (Topic 40-79)
    # Microeconomics Year 1 (Topic 40-49)
    40: {
        'name': 'Nature of Economics',
        'subtopics': [
            'Economics as a Social Science',
            'Positive and Normative Economic Statements',
            'The Economic Problem',
            'Production Possibility Frontiers',
            'Specialisation and Division of Labour',
            'Economic Systems'
        ]
    },
    41: {
        'name': 'Demand and Supply',
        'subtopics': [
            'Rational Decision Making',
            'Demand',
            'Price Elasticity of Demand',
            'Income and Cross Elasticity of Demand',
            'Supply',
            'Elasticity of Supply'
        ]
    },
    42: {
        'name': 'Market Mechanisms and Consumer Behaviour',
        'subtopics': [
            'Price Determination',
            'Price Mechanism',
            'Consumer and Producer Surplus',  
            'Alternative Views of Consumer Behaviour' 
        ]
    },
    43: {
        'name': 'Market Failure',
        'subtopics': [
            'Types of Market Failure',
            'Externalities',
            'Public Goods',
            'Information Gaps'
        ]
    },
    44: {
        'name': 'Government Intervention (1)',
        'subtopics': [
            'Government Intervention in Markets',  
            'Government Failure'  
        ]
    },
    # Macroeconomics Year 1 (Topic 50-59)
    50: {
        'name': 'Measures of Economic Performance',
        'subtopics': [
            'Economic Growth',
            'Inflation',
            'Employment and Unemployment',
            'Balance of Payments'
        ]
    },
    51: {
        'name': 'Aggregate Demand',
        'subtopics': [
            'Components of AD',
            'Consumption',
            'Investment',
            'Government Spending',
            'Net Exports'
        ]
    },
    52: {
        'name': 'Aggregate Supply',
        'subtopics': [
            'Short-run AS',
            'Long-run AS',
            'AS/AD Equilibrium',
            'Economic Shocks'
        ]
    },
    53: {
        'name': 'National Income',
        'subtopics': [
            'Circular Flow of Income',
            'Injections and Withdrawals',
            'Equilibrium',
            'Multiplier Effect'
        ]
    },
    54: {
        'name': 'Economic Growth',
        'subtopics': [
            'Causes of Growth',
            'Output Gaps',
            'Trade Cycle',
            'Living Standards'
        ]
    },
    55: {
        'name': 'Macroeconomic Objectives and Policies',
        'subtopics': [
            'Government Objectives',
            'Policy Instruments',
            'Policy Conflicts',
            'Supply-side Policies'
        ]
    },

    #Microeconomics Year 2 (Topic 60-69)
    60: {
        'name': 'Business Growth',
        'subtopics': [
            'Sizes and Types of Firms',
            'Business Growth',
            'Demergers',
        ]
    },
    61: {
        'name': 'Business Objectives',
        'subtopics': [
            ' Business Objectives'
        ]
    },
    62: {
        'name': 'Revenues, Costs and Profits',
        'subtopics': [
            'Revenue',
            'Costs',
            'Economies and diseconomies of scale',
            'Normal Profit, Supernormal Profit and losses'
        ]
    },
    63: {
        'name': 'Market Structures',
        'subtopics': [
            'Efficiency',
            'Perfect competition',
            'Monopolistic Competition',
            'Oligopoly',
            'Monopoly',
            'Monopsony',
            'Contestability'
        ]
    },
    64: {
        'name': 'Labour Markets',
        'subtopics': [
            'Demand for Labour',
            'Supply of Labour',
            'Wage Determination',
            'Labour Market Issues'
        ]
    },
    65: {
        'name': 'Government Intervention (2)',
        'subtopics': [
            'Government Intervention',
            'The impact of government intervention'
        ]
    },
    
    #Macroeconomics Year 2 (Topic 70-79)
    70: {
        'name': 'International Economics Policy',
        'subtopics': [
            'Globalisation',
            'Specialisation and trade',
            'Patterns of trade',
            'Terms of trade',
            'Trading blocs and the WTO',
            'Restriction on free trade',
            'The Balance of Payments',
            'Exchange Rates',
            'International competitiveness'
        ]
    },
    71: {
        'name': 'Poverty and Inequality',
        'subtopics': [
            'Absolute and relative poverty',
            'Inequality',
        ]
    },
    72: {
        'name': 'Emerging and Developing Economies',
        'subtopics': [
            'Measures of development',
            'Factors influencing growth and development',
            'Strategies influencing growth and development',
        ]
    },
    73: {
        'name': 'The Financial Sector',
        'subtopics': [
            'Role of financial markets',
            'Market failure in the financial sector',
            'Role of central banks',
        ]
    },
    74: {
        'name': 'Role of the State in the Macroeconomy',
        'subtopics': [
            'Public expenditure',
            'Taxation',
            'Public sector finances',
            'Macroeconomic policies in a global context',
        ]
    },
    #Computer Science Topics (Topic 80-119)
    80: {
        'name': 'Yet to be added',
        'subtopics': [
            'Yet to be added',
        ]
    },
}

@app.route('/topics/<int:topic_id>/subtopics')
def view_subtopics(topic_id):
    if 'username' not in session:
        flash('You need to login first!')
        return redirect(url_for('login'))
    
    # Get topic data or return 404 if topic doesn't exist
    topic = topic_data.get(topic_id)
    if not topic:
        flash('Topic not found!')
        return redirect(url_for('dashboard'))
    
    if 1 <= topic_id <= 39:      
        # Maths Course
        course_id = 1
    elif 40 <= topic_id <= 79:   
        # Economics Course
        course_id = 2
    elif 80 <= topic_id <= 119:  
        # Computer Science Course   
        course_id = 3
    else:
        # Defaults to Maths Course
        course_id = 1

    previous_url = url_for('view_course', course_id=course_id)
    
    return render_template('subtopics.html', 
                         topic_name=topic['name'],
                         subtopics=topic['subtopics'],
                         topic_id=topic_id,
                         previous_url=previous_url,
                         hide_nav=True,
                         title="StudyCore")

@app.route('/topics/<int:topic_id>/flashcards/<path:subtopic>')
def view_flashcards(topic_id, subtopic):
    if 'username' not in session:
        flash('You need to login first!')
        return redirect(url_for('login'))

    # Get flashcards for the selected topic
    content = {
        'flashcards': flashcards_by_year.get(subtopic, [])
    }
    
    # Determine course_id based on topic_id range
    if 1 <= topic_id <= 39:      # Maths
        course_id = 1
    elif 40 <= topic_id <= 79:   # Economics
        course_id = 2
    elif 80 <= topic_id <= 119:  # Computer Science
        course_id = 3
    else:
        course_id = 2  # Default to Economics
    
    previous_url = url_for('view_course', course_id=course_id)
    
    return render_template('flashcards.html', 
                         topic_id=topic_id,
                         course_id=course_id,
                         subtopic=subtopic,
                         content=content,
                         previous_url=previous_url,
                         hide_nav=True)

@app.route('/topics/<int:topic_id>/quizzes/<path:subtopic>')
def view_quizzes(topic_id, subtopic):
    if 'username' not in session:
        flash('You need to login first!')
        return redirect(url_for('login'))
    
    # Get topic data
    topic_data_dict = topic_data.get(topic_id, {})
    topic_name = topic_data_dict.get('name', '')
    
    # Get user's quiz scores
    conn = sqlite3.connect('user_database.db')
    cursor = conn.cursor()
    user_id = session['user_id']
    
    try:
        # Get all subtopics for this topic and their scores
        subtopics = []
        for (tid, sub), content in notes_content.items():
            if tid == topic_id:
                # Check if the quiz has been attempted (any score counts)
                cursor.execute('''
                    SELECT COUNT(*) 
                    FROM quiz_scores 
                    WHERE user_id = ? AND topic_id = ? AND subtopic = ?
                ''', (user_id, tid, sub))
                result = cursor.fetchone()
                attempted = result[0] > 0 if result else False
                
                subtopics.append({
                    'name': sub,
                    'description': f"Test your knowledge about {sub}",
                    'completed': attempted  # Mark as completed if any attempt exists
                })
    finally:
        conn.close()
    
    previous_url = url_for('view_subtopics', topic_id=topic_id)
    
    return render_template('quizzes_list.html', 
                         topic_id=topic_id,
                         topic_name=topic_name,
                         subtopics=subtopics,
                         previous_url=previous_url,
                         hide_nav=True)

@app.route('/topics/<int:topic_id>/quiz/<path:subtopic>')
def view_quiz(topic_id, subtopic):
    if 'username' not in session:
        flash('You need to login first!')
        return redirect(url_for('login'))
    
    # Generate quiz questions using the AI-based system with topic and subtopic
    questions = generate_quiz(topic_id, subtopic, 5)  # Always generate 5 questions
    
    # Keep generating questions until we have at least 5
    attempts = 0
    while len(questions) < 5 and attempts < 3:
        additional_questions = generate_quiz(topic_id, subtopic, 5 - len(questions))
        questions.extend(additional_questions)
        attempts += 1
    
    if len(questions) < 5:
        flash('Unable to generate enough questions for this topic. Please try again later.')
        return redirect(url_for('view_quizzes', topic_id=topic_id, subtopic=subtopic))
    
    # Store questions in session for checking answers later
    session['quiz_questions'] = questions
    session['quiz_score'] = 0
    session['quiz_current_question'] = 0
    session['quiz_total_questions'] = len(questions)
    
    # Store topic_id and subtopic in session for score tracking
    session['quiz_topic_id'] = topic_id
    session['quiz_subtopic'] = subtopic
    
    previous_url = url_for('view_quizzes', topic_id=topic_id, subtopic=subtopic)
    
    # Get the first question
    current_question = questions[0]
    
    return render_template('quiz.html',
                         topic_id=topic_id,
                         subtopic=subtopic,
                         current_question=1,
                         total_questions=len(questions),
                         question=current_question['question'],
                         question_type=current_question['type'],
                         previous_url=previous_url,
                         hide_nav=True)

@app.route('/check_answer', methods=['POST'])
def check_answer():
    if 'username' not in session:
        return jsonify({'error': 'You need to login first!'}), 401
    
    # Get quiz data from session
    questions = session.get('quiz_questions', [])
    current_question = session.get('quiz_current_question', 0)
    quiz_score = session.get('quiz_score', 0)
    total_questions = session.get('quiz_total_questions', 0)
    
    if not questions or current_question >= len(questions):
        return jsonify({'error': 'No active quiz or invalid question'}), 400
    
    # Get user's answer and current question
    user_answer = request.form.get('answer', '').strip()
    question = questions[current_question]
    
    # Add a small delay to allow for better answer processing (500ms)
    import time
    time.sleep(0.5)
    
    # Ensure we have the correct answer for this specific question
    correct_answer = question.get('correct_answer', "")
    question_text = question.get('question', "")
    
    # Empty answer handling - mark as incorrect but don't show error
    if not user_answer:
        is_correct = False
        feedback = "✗ Not quite right."
        current_question += 1
        session['quiz_current_question'] = current_question
        
        # Prepare response for empty answer
        response = {
            'correct': is_correct,
            'feedback': feedback,
            'correct_answer': correct_answer,
            'current_score': quiz_score,
            'current_question': current_question,
            'total_questions': total_questions,
            'completed': current_question >= total_questions
        }
        
        return jsonify(response)
        
    # Use the question text to get a more accurate model answer if possible
    model_answer = None
    if question_text:
        model_answer = answer_checker.get_model_answer(question_text)
    
    # If we got a model answer and it's different from the stored correct answer,
    # verify which one is more appropriate based on the question text
    if model_answer and model_answer != correct_answer:
        # Use text similarity to determine which answer is better for this question
        q_to_model = answer_checker.calculate_text_similarity(question_text.lower(), model_answer.lower())
        q_to_stored = answer_checker.calculate_text_similarity(question_text.lower(), correct_answer.lower())
        
        # If model answer is significantly more relevant, use it instead
        if q_to_model > q_to_stored + 0.2:
            correct_answer = model_answer
            # Update the question in the session for future reference
            question['correct_answer'] = model_answer
            questions[current_question] = question
            session['quiz_questions'] = questions
    
    # Now check the user's answer using whichever correct answer is more appropriate
    is_correct, feedback, _ = answer_checker.check_answer({'question': question_text, 'correct_answer': correct_answer}, user_answer)
    
    if is_correct:
        quiz_score += 1
        session['quiz_score'] = quiz_score
    
    # Move to next question
    current_question += 1
    session['quiz_current_question'] = current_question
    
    # Simplify feedback
    if is_correct:
        feedback = "✓ Correct! Well done!"
    else:
        feedback = "✗ Not quite right."
    
    # Prepare response
    response = {
        'correct': is_correct,
        'feedback': feedback,
        'correct_answer': correct_answer,
        'current_score': quiz_score,
        'current_question': current_question,
        'total_questions': total_questions,
        'completed': current_question >= total_questions
    }
    
    # If quiz is completed, store the score in the database
    if current_question >= total_questions:
        # Get topic_id and subtopic from session
        topic_id = session.get('quiz_topic_id')
        subtopic = session.get('quiz_subtopic')
        
        if topic_id and subtopic:
            user_id = session.get('user_id')
            percentage = (quiz_score / total_questions) * 100
            
            # Store in database
            try:
                conn = sqlite3.connect('user_database.db')
                cursor = conn.cursor()
                
                # Check if a score already exists for this user/topic/subtopic
                cursor.execute('''
                    SELECT id FROM quiz_scores 
                    WHERE user_id = ? AND topic_id = ? AND subtopic = ?
                ''', (user_id, topic_id, subtopic))
                
                existing_record = cursor.fetchone()
                
                if existing_record:
                    # Update existing record
                    cursor.execute('''
                        UPDATE quiz_scores 
                        SET score = ?, total_questions = ?, percentage = ?, date_taken = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (quiz_score, total_questions, percentage, existing_record[0]))
                else:
                    # Insert new record
                    cursor.execute('''
                        INSERT INTO quiz_scores (user_id, topic_id, subtopic, score, total_questions, percentage)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (user_id, topic_id, subtopic, quiz_score, total_questions, percentage))
                
                conn.commit()
            except sqlite3.Error as e:
                print(f"Database error: {e}")
            finally:
                conn.close()
    
    return jsonify(response)

@app.route('/next_question', methods=['GET'])
def next_question():
    if 'username' not in session:
        flash('You need to login first!')
        return redirect(url_for('login'))
    
    # Get quiz data from session
    questions = session.get('quiz_questions', [])
    current_question = session.get('quiz_current_question', 0)
    total_questions = session.get('quiz_total_questions', 0)
    
    if not questions or current_question >= total_questions:
        flash('Quiz completed or no active quiz')
        return redirect(url_for('dashboard'))
    
    topic_id = request.args.get('topic_id')
    subtopic = request.args.get('subtopic')
    previous_url = url_for('view_quizzes', topic_id=topic_id, subtopic=subtopic)
    
    return render_template('quiz.html',
                         topic_id=topic_id,
                         subtopic=subtopic,
                         current_question=current_question + 1,
                         total_questions=total_questions,
                         question=questions[current_question]['question'],
                         previous_url=previous_url,
                         hide_nav=True)

# Keep this route and update it
@app.route('/topics/<int:topic_id>/notes_list/<path:subtopic>')
def view_notes_list(topic_id, subtopic):
    if 'username' not in session:
        flash('You need to login first!')
        return redirect(url_for('login'))
    
    # Get topic data
    topic_data_dict = topic_data.get(topic_id, {})
    topic_name = topic_data_dict.get('name', '')
    subtopics = topic_data_dict.get('subtopics', [])
    
    previous_url = url_for('view_subtopics', topic_id=topic_id)
    
    return render_template('notes_list.html', 
                         topic_id=topic_id,
                         topic_name=topic_name,
                         subtopics=subtopics,
                         previous_url=previous_url,
                         hide_nav=True)

@app.route('/topics/<int:topic_id>/notes/<path:subtopic>')
def view_notes(topic_id, subtopic):
    if 'username' not in session:
        flash('You need to login first!')
        return redirect(url_for('login'))
    
    # Get topic data
    topic_data_dict = topic_data.get(topic_id, {})
    topic_name = topic_data_dict.get('name', '')
    
    # Get notes content for this topic and subtopic
    notes = None
    
    # Try exact match first
    if (topic_id, subtopic) in notes_content:
        notes = notes_content[(topic_id, subtopic)]
    else:
        # Try with normalized subtopic (lowercase, no extra spaces)
        normalised_subtopic = subtopic.lower().strip()
        
        # Try partial matches
        for (tid, sub), content in notes_content.items():
            if tid == topic_id:
                # If topic IDs match, try various string matching approaches
                if sub.lower().strip() == normalised_subtopic:
                    notes = content
                    break
                # Check if the subtopic contains our search term or vice versa
                elif normalised_subtopic in sub.lower() or sub.lower() in normalised_subtopic:
                    notes = content
                    break
    
    previous_url = url_for('view_notes_list', topic_id=topic_id, subtopic=subtopic)
    
    return render_template('notes.html', 
                         topic_id=topic_id,
                         topic_name=topic_name,
                         subtopic=subtopic,
                         notes=notes,
                         previous_url=previous_url,
                         hide_nav=True)

@app.route('/topics/<int:topic_id>/practice/<path:subtopic>')
def view_practice(topic_id, subtopic):
    if 'username' not in session:
        flash('You need to login first!')
        return redirect(url_for('login'))
    
    previous_url = url_for('view_subtopics', topic_id=topic_id)
    return render_template('practice.html', 
                         topic_id=topic_id,
                         subtopic=subtopic,
                         previous_url=previous_url,
                         hide_nav=True)

@app.route('/personalised_test/<int:course_id>')
def personalised_test(course_id):
    if 'username' not in session:
        flash('You need to login first!')
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    
    # Connect to database to get user's quiz scores
    conn = sqlite3.connect('user_database.db')
    cursor = conn.cursor()
    
    try:
        # New code - counting total quiz attempts
        cursor.execute('''
            SELECT COUNT(*)
            FROM quiz_scores
            WHERE user_id = ?
        ''', (user_id,))
        
        completed_topics = cursor.fetchone()[0]
        
        # User needs at least 3 completed topics to take a personalised test
        can_take_test = completed_topics >= 3
        
        previous_url = url_for('view_course', course_id=course_id)
        
        return render_template('personalised_test.html',
                             course_id=course_id,
                             can_take_test=can_take_test,
                             previous_url=previous_url,
                             hide_nav=True)
    
    except sqlite3.Error as e:
        flash(f'Database error: {str(e)}')
        return redirect(url_for('dashboard'))
    finally:
        conn.close()

@app.route('/start_personalised_test/<int:course_id>')
def start_personalised_test(course_id):
    if 'username' not in session:
        flash('You need to login first!')
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    
    # Connect to database to get user's quiz scores
    conn = sqlite3.connect('user_database.db')
    cursor = conn.cursor()
    
    try:
        # Get all subtopics with their scores for this user
        cursor.execute('''
            SELECT topic_id, subtopic, percentage
            FROM quiz_scores
            WHERE user_id = ?
        ''', (user_id,))
        
        all_scores = cursor.fetchall()
        
        # Categorise subtopics by proficiency level
        weak_subtopics = []     # <60%
        medium_subtopics = []   # 60-80%
        strong_subtopics = []   # >80%
        
        for topic_id, subtopic, percentage in all_scores:
            if percentage < 60:
                weak_subtopics.append((topic_id, subtopic))
            elif percentage < 80:
                medium_subtopics.append((topic_id, subtopic))
            else:
                strong_subtopics.append((topic_id, subtopic))
        
        # Generate personalised test with priority on weak topics
        test_questions = []
        
        # Include questions from weak topics (70% of test)
        if weak_subtopics:
            for topic_id, subtopic in weak_subtopics:
                # Find notes content for this topic
                if (topic_id, subtopic) in notes_content:
                    notes = notes_content[(topic_id, subtopic)]
                    # Generate questions using AI system
                    questions = generate_quiz(topic_id, subtopic, 3)  # Generate 3 questions per weak topic
                    test_questions.extend(questions)
        
        # Fill remaining with medium and strong topics
        remaining_slots = 10 - len(test_questions)
        if remaining_slots > 0 and medium_subtopics:
            for topic_id, subtopic in medium_subtopics[:remaining_slots]:
                if (topic_id, subtopic) in notes_content:
                    notes = notes_content[(topic_id, subtopic)]
                    questions = generate_quiz(topic_id, subtopic, 1)  # 1 question per medium topic
                    test_questions.extend(questions)
                    remaining_slots -= 1
                    if remaining_slots <= 0:
                        break
        
        # If still have slots, add some from strong topics for reinforcement
        if remaining_slots > 0 and strong_subtopics:
            for topic_id, subtopic in strong_subtopics[:remaining_slots]:
                if (topic_id, subtopic) in notes_content:
                    notes = notes_content[(topic_id, subtopic)]
                    questions = generate_quiz(topic_id, subtopic, 1)  # 1 question per strong topic
                    test_questions.extend(questions)
        
        # If no quiz scores yet or not enough questions, provide a general test
        if len(test_questions) < 5:
            # Generate a general test with questions from various topics
            cursor.execute('''
                SELECT DISTINCT topic_id
                FROM quiz_questions
                WHERE topic_id IS NOT NULL
                LIMIT 5
            ''')
            
            general_topics = cursor.fetchall()
            
            for (topic_id,) in general_topics:
                # Generate questions from topics without using subtopics
                # Use a default subtopic name for consistent access to notes_content
                default_subtopic = f"Topic_{topic_id}"
                if (topic_id, default_subtopic) in notes_content:
                    notes = notes_content[(topic_id, default_subtopic)]
                    questions = generate_quiz(topic_id, default_subtopic, 2)  # 2 questions per topic
                    test_questions.extend(questions)
                else:
                    # Try to find any subtopic for this topic_id
                    for (tid, sub), content in notes_content.items():
                        if tid == topic_id:
                            questions = generate_quiz(tid, sub, 2)
                            test_questions.extend(questions)
                            break
        
        # Limit to 10 questions max and shuffle
        random.shuffle(test_questions)
        test_questions = test_questions[:10]
        
        # If no questions were generated, provide a message
        if not test_questions:
            flash('Not enough data to generate a personalised test. Please take some quizzes first.')
            return redirect(url_for('dashboard'))
        
        # Store questions in session
        session['quiz_questions'] = test_questions
        session['quiz_score'] = 0
        session['quiz_current_question'] = 0
        session['quiz_total_questions'] = len(test_questions)
        session['quiz_topic_id'] = 0  # Special value for personalised test
        session['quiz_subtopic'] = 'Personalised Test'
        
        # Redirect to the first question
        return render_template('quiz.html',
                             topic_id=course_id,
                             subtopic="Personalised Test",
                             current_question=1,
                             total_questions=len(test_questions),
                             question=test_questions[0]['question'],
                             previous_url=url_for('view_course', course_id=course_id),
                             hide_nav=True)
    
    except sqlite3.Error as e:
        flash(f'Database error: {str(e)}')
        return redirect(url_for('dashboard'))
    finally:
        conn.close()

#Handles the user profile page     
@app.route('/user_profile')
def user_profile():
    if 'username' not in session:
        flash('You need to login first to access your profile!')
        return redirect(url_for('login'))
    
    previous_url = request.args.get('previous_url', url_for('dashboard'))  # Default to dashboard

    user_id = session['user_id']
    conn = sqlite3.connect('user_database.db')
    cursor = conn.cursor()

    # Retrieve user information
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()

    conn.close()
    return render_template('user_profile.html', hide_nav=True, user_data=user_data, previous_url=previous_url)

#Handles the settings page  
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'username' not in session:
        flash('You need to login first to access settings!', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = sqlite3.connect('user_database.db')
    cursor = conn.cursor()

    try:
        if request.method == 'POST':
            new_username = request.form.get('new_username', '').strip()
            new_password = request.form.get('new_password', '').strip()

            # Check if at least one field is filled
            if not new_username and not new_password:
                flash('Please enter a new username or password to update.', 'error')
                return redirect(url_for('settings'))

            # Validate inputs if provided
            if new_username:
                if len(new_username) < 5:
                    flash('Username must be at least 5 characters long', 'error')
                    return redirect(url_for('settings'))
                
                # Check if username is already taken by another user
                cursor.execute('SELECT id FROM users WHERE username = ? AND id != ?', 
                            (new_username, user_id))
                if cursor.fetchone():
                    flash('Username is already taken', 'error')
                    return redirect(url_for('settings'))

            if new_password:
                if len(new_password) < 8:
                    flash('Password must be at least 8 characters long', 'error')
                    return redirect(url_for('settings'))

            # Update database if validations pass
            try:
                if new_username:
                    cursor.execute('UPDATE users SET username = ? WHERE id = ?', 
                                (new_username, user_id))
                    session['username'] = new_username  # Update session
                
                if new_password:
                    cursor.execute('UPDATE users SET password = ? WHERE id = ?', 
                                (new_password, user_id))

                conn.commit()
                flash('Settings updated successfully!', 'success')
                return redirect(url_for('user_profile'))
            except Exception as e:
                conn.rollback()
                flash(f'An error occurred: {e}', 'error')
                return redirect(url_for('settings'))

        # Fetch current user data to populate the form
        cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
        user_data = cursor.fetchone()

        previous_url = url_for('user_profile')
        return render_template('settings.html', hide_nav=True, user_data=user_data, previous_url=previous_url)

    except Exception as e:
        flash(f'An error occurred: {e}', 'error')
        return redirect(url_for('dashboard'))

    finally:
        conn.close()

#Handles the theme preference
@app.route('/set_theme', methods=['POST'])
def set_theme():
    theme = request.json.get('theme')
    session['theme'] = theme
    return jsonify({'status': 'success'})

@app.route('/progress_report/<int:course_id>')
def progress_report(course_id):
    if 'username' not in session:
        flash('You need to login first!')
        return redirect(url_for('login'))

    conn = sqlite3.connect('user_database.db', check_same_thread=False)
    cursor = conn.cursor()
    user_id = session['user_id']

    try:
        # Get 5 weakest subtopics (lowest percentage scores)
        cursor.execute('''
            SELECT topic_id, subtopic, percentage, 
                   datetime(date_taken) as formatted_date
            FROM quiz_scores
            WHERE user_id = ? AND topic_id BETWEEN 40 AND 79
            GROUP BY subtopic
            HAVING MAX(date_taken)
            ORDER BY percentage ASC
            LIMIT 5
        ''', (user_id,))
        weak_topics = cursor.fetchall()

        # Get 6 most recent quiz scores
        cursor.execute('''
            SELECT topic_id, subtopic, score, total_questions, percentage,
                   datetime(date_taken) as formatted_date
            FROM quiz_scores
            WHERE user_id = ? AND topic_id BETWEEN 40 AND 79
            ORDER BY date_taken DESC
            LIMIT 6
        ''', (user_id,))
        recent_scores = cursor.fetchall()

        return render_template('progress_report.html',
                             weak_topics=weak_topics,
                             recent_scores=recent_scores,
                             course_id=course_id,
                             hide_nav=True,
                             previous_url=url_for('view_course', course_id=course_id))

    except Exception as e:
        flash(f'An error occurred: {e}')
        return redirect(url_for('view_course', course_id=course_id))

    finally:
        conn.close()

#Secret admin activation route
@app.route('/activate_admin/<token>')
def activate_admin(token):
    if 'username' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
    
    # Use a secure token
    if token != 'admin_token':
        flash('Invalid activation token.', 'error')
        return redirect(url_for('dashboard'))
    
    conn = sqlite3.connect('user_database.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (session['user_id'],))
        conn.commit()
        flash('Admin privileges activated successfully!', 'success')
    except Exception as e:
        flash(f'Error activating admin privileges: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('admin_dashboard'))

#Admin dashboard
@app.route('/admin')
@admin_required
def admin_dashboard():
    previous_url = url_for('dashboard')
    return render_template('admin_dashboard.html', hide_nav=True, previous_url=previous_url)

#Manage users
@app.route('/admin/users', methods=['GET', 'POST'])
@admin_required
def manage_users():
    conn = sqlite3.connect('user_database.db')
    cursor = conn.cursor()
    
    if request.method == 'POST':
        action = request.form.get('action')
        user_id = request.form.get('user_id')
        
        if action == 'delete':
            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            cursor.execute('DELETE FROM saved_courses WHERE user_id = ?', (user_id,))
            cursor.execute('DELETE FROM course_progress WHERE user_id = ?', (user_id,))
            cursor.execute('DELETE FROM quiz_scores WHERE user_id = ?', (user_id,))
            conn.commit()
            flash('User deleted successfully.', 'success')
        
        elif action == 'toggle_admin':
            cursor.execute('UPDATE users SET is_admin = NOT is_admin WHERE id = ?', (user_id,))
            conn.commit()
            flash('Admin status toggled successfully.', 'success')
    
    cursor.execute('SELECT id, username, is_admin FROM users')
    users = cursor.fetchall()
    conn.close()
    
    previous_url = url_for('admin_dashboard')
    return render_template('manage_users.html', users=users, hide_nav=True, previous_url=previous_url)

#Manage database
@app.route('/admin/database')
@admin_required
def manage_database():
    conn = sqlite3.connect('user_database.db')
    cursor = conn.cursor()
    
    # Get all database statistics
    cursor.execute('SELECT COUNT(*) FROM users')
    user_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM saved_courses')
    saved_courses_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM quiz_scores')
    quiz_scores_count = cursor.fetchone()[0]
    
    stats = {
        'users': user_count,
        'saved_courses': saved_courses_count,
        'quiz_scores': quiz_scores_count
    }
    
    # Get all users
    cursor.execute('SELECT id, username, is_admin FROM users')
    users = cursor.fetchall()
    
    # Get all courses
    cursor.execute('SELECT * FROM courses')
    courses = cursor.fetchall()
    
    # Get quiz scores with user and topic info
    cursor.execute('''
        SELECT qs.id, u.username, qs.subtopic, qs.percentage, 
               datetime(qs.date_taken) as formatted_date
        FROM quiz_scores qs
        JOIN users u ON qs.user_id = u.id
        ORDER BY qs.date_taken DESC
    ''')
    quiz_scores = cursor.fetchall()
    
    # Get saved courses with user and course info
    cursor.execute('''
        SELECT u.username, c.course_name
        FROM saved_courses sc
        JOIN users u ON sc.user_id = u.id
        JOIN courses c ON sc.course_id = c.id
    ''')
    saved_courses = cursor.fetchall()
    
    conn.close()
    
    return render_template('manage_database.html', 
                         stats=stats,
                         users=users,
                         courses=courses,
                         quiz_scores=quiz_scores,
                         saved_courses=saved_courses,
                         hide_nav=True)

#Manage courses
@app.route('/admin/courses', methods=['GET', 'POST'])
@admin_required
def manage_courses():
    conn = sqlite3.connect('user_database.db')
    cursor = conn.cursor()
    
    if request.method == 'POST':
        action = request.form.get('action')
        course_id = request.form.get('course_id')
        
        if action == 'add':
            name = request.form.get('name')
            description = request.form.get('description')
            cursor.execute('INSERT INTO courses (course_name, description) VALUES (?, ?)',
                         (name, description))
            conn.commit()
            flash('Course added successfully.', 'success')
            
        elif action == 'delete':
            cursor.execute('DELETE FROM courses WHERE id = ?', (course_id,))
            cursor.execute('DELETE FROM saved_courses WHERE course_id = ?', (course_id,))
            cursor.execute('DELETE FROM course_progress WHERE course_id = ?', (course_id,))
            conn.commit()
            flash('Course deleted successfully.', 'success')
    
    cursor.execute('SELECT * FROM courses')
    courses = cursor.fetchall()
    conn.close()
    
    previous_url = url_for('admin_dashboard')
    return render_template('manage_courses.html', courses=courses, hide_nav=True, previous_url=previous_url)

#Starts the program
if __name__ == '__main__':
    setup_static_dirs()
    initialise_user_database()
    app.run(debug=True)
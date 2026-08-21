# Online Examination System (MVP)
Course Code: CSE 3206 | Course Name: Software Engineering Sessional
Rajshahi University of Engineering & Technology (RUET)

This repository contains the Minimum Viable Product (MVP) of the Online Examination System built by **Group #05**, **Section A (2nd 30)**.

## Installation & Deployment

Follow these steps to set up and run the sessional prototype locally:

1. **Set up Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize Database and Start Application:**
   The SQLite database (`online_exam.db`) is automatically initialized using the `schema.sql` template on server start:
   ```bash
   python app.py
   ```

4. **Access the Application:**
   Open your browser and navigate to `http://127.0.0.1:5000`.

## Git & GitHub Collaboration Guidelines

Branch names and responsibilities are allocated as follows:
- `feature/auth-dashboard`: Authentication and main layout dashboards.
- `feature/exam-management`: Teacher assessment creation and Question CRUD modules.
- `feature/exam-taking`: Student live exam countdown client, validation, and grading engine.

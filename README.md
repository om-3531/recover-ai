# Smart AI Resume Analyzer & Career Platform

**Next-Generation AI Career Acceleration & ATS Intelligence Platform**

Built with **Python**, **Streamlit**, **Plotly**, **SQLite**, and **Deterministic NLP / Generative AI Engine**.

---

## 🌟 Key Highlights & Modules

### 1. 📄 AI Resume Intelligence & ATS Scoring
- **Deterministic Multi-Axis Evaluation**: Calculates Overall Score (/100), ATS Parsability Score, Technical Skills Breadth, Experience & Project Impact, Education Score, Keyword Density, and Formatting Quality.
- **Interactive Visualizations**: Circular score gauges and 6-axis polar radar charts powered by Plotly.
- **Automated Insights**: Identifies concrete strengths, areas for improvement, missing sections, and actionable recommendations.
- **Report Export**: Instant download of comprehensive PDF audit reports and text summaries.

### 2. 🎯 Job Description Match Analyzer
- **Direct Semantic & Keyword Comparison**: Paste any job description to compute real-time technical match percentages.
- **Skill Overlap**: Visual breakdown of matched skills vs. missing target technologies.
- **Tailoring Suggestions**: Generates targeted phrasing and section enhancements for specific job openings.

### 3. 🧠 AI Skill Gap Analyzer
- **Industry Role Benchmarks**: Compares candidate profile against benchmarks for AI/ML Engineer, Full-Stack Developer, Android Developer, Data Scientist, Cloud/DevOps, and Software Engineer.
- **Proficiency Estimation & Priority Ranking**: Ranks missing skills into High/Medium/Low priority tiers with estimated learning hours.
- **3-Phase Learning Roadmap**: Tailored curriculum spanning Beginner, Intermediate, and Advanced milestones.

### 4. 🗺️ 30-60-90 Day Career Action Roadmap
- **Structured Transition Plans**: Detailed 30-day foundational, 60-day systems integration, and 90-day production deployment plans.
- **Milestones**: Daily practice routines, LeetCode/interview preparation targets, portfolio capstone projects, and resume updates.

### 5. ✨ AI Resume Bullet Improver
- **STAR & Google XYZ Framework**: Transforms weak/passive draft sentences into high-impact, ATS-optimized bullet points using power action verbs and quantifiable metrics.
- **Before / After Comparison**: Interactive side-by-side diff cards with tips.

### 6. ✍️ AI Cover Letter Generator
- **Grounded Generation**: Creates personalized, tailored cover letters referencing actual candidate projects, education, and internship achievements.
- **Export Options**: 1-click download as formatted PDF or plain text (.txt).

### 7. 📚 AI Interview Preparation
- **Comprehensive Question Bank**: Technical, HR, Behavioral, and Project questions with difficulty levels (Easy, Medium, Hard).
- **Answer Blueprints**: Includes "Why the interviewer asks this", structured sample answers, and key points to mention.

### 8. 🤖 Interactive AI Mock Interview
- **Realistic Practice Simulation**: Step-by-step Q&A flow with the AI interviewer.
- **Multi-Dimensional Answer Grading**: Evaluates Technical Accuracy, Communication Clarity, Confidence & Tone, Relevance, and Completeness.

### 9. 📊 Career Analytics Dashboard
- **Real-Time KPIs**: Tracks active resume score, ATS rating, job matches run, and mock interview grades.
- **Visual Analytics**: Interactive line charts of score progression over time, technical domain distribution donut charts, and application history logs.

### 10. 📝 ATS Resume Builder
- **Structured Form Builder**: Interactive inputs for contact info, summary, education, experience, projects, skills, and honors.
- **Live Preview & Export**: Live single-page ATS preview with instant PDF and TXT downloads.

### 11. 🔍 Job Search & Recommendations
- **Simulated Tech Job Openings**: Explore current software engineering and AI openings with 1-click instant match audits.

### 12. 👩‍💻 Professional Portfolio (Prajakta Bhambar)
- **Verified Candidate Profile**:
  - **Headline**: Computer Engineering Student | Software Developer | AI/ML Enthusiast
  - **Education**: B.Tech in Computer Engineering (SNJB's Late Sau. Kantabai Bhavarlalji Jain COE, Chandwad - Expected 2028), Diploma in Computer Engineering (88.63%), SSC (90.00%)
  - **Internship**: Android Development Intern (Cognifyz IT Solutions Pvt. Ltd.)
  - **Key Projects**: PersonaOS (Agentic AI Goal-Achievement Assistant), AI-Driven Smart Transportation System (YOLO/OpenCV), Student Grade Management App (Android/Java/SQLite)
  - **Skills**: C, C++, Java, Python, SQL, Machine Learning, Computer Vision, YOLO, Agentic AI, HTML, CSS, JavaScript, PHP, MySQL, Git, GitHub, Android Studio, SQLite
  - **Achievements**: First Runner-Up – Hackspectra 2.0 Hackathon, Finalist – Hack Better Than Me Hackathon, CampusCrew 100K Milestone Honor Certificate

### 13. ⭐ User Feedback & Reviews
- **Community Ratings & Admin Review**: Allows users to rate features and leave comments with SQLite persistence.

### 14. 🔐 Authentication & Session Persistence
- **Secure Hashing**: User registration, login, and admin roles with SHA-256 + salt password security.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 2. Run Headless Smoke Test
```bash
python tests/smoke_test.py
```

### 3. Launch Application
```bash
python -m streamlit run app.py
```

Open your browser at: **http://localhost:8501**

---

## 🗄️ Database Architecture
All application data is persisted locally in an SQLite database located at `data/career_platform.db`:
- `users`: User profiles, hashed credentials, and roles.
- `resumes`: Raw text and parsed entity structures.
- `resume_analyses`: Multi-axis scores, strengths, and recommendations.
- `job_matches`: Job titles, match percentages, matched/missing skills.
- `skill_gaps`: Target role gaps and 3-phase roadmaps.
- `career_roadmaps`: 30-60-90 day milestone plans.
- `mock_interviews`: Session histories, scores, and evaluations.
- `cover_letters`: Saved cover letters.
- `feedback`: User ratings and platform reviews.

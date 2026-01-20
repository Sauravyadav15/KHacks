<<<<<<< HEAD
# KingHacks26 - Storyteller Test Bench

## Setup Instructions

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   ```

3. Activate the virtual environment:
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - Mac/Linux:
     ```bash
     source venv/bin/activate
     ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Run the backend server:
   ```bash
   uvicorn main:app --reload
   ```

The backend will be running at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Run the development server:
   ```bash
   npm run dev
   ```

The frontend will be running at `http://localhost:5173` (or the port shown in the terminal)

## Project Structure

- `backend/` - FastAPI backend
  - `routers/` - API route handlers
    - `__init__.py` - Package initialization
    - `student.py` - Student chat endpoint
  - `main.py` - Main application file
  - `requirements.txt` - Python dependencies
- `frontend/` - React + TypeScript + Vite
  - `src/`
    - `pages/` - Page components (Student.tsx, Teacher.tsx)
    - `router/` - React Router configuration (index.tsx)
    - `App.tsx` - Main app layout with tabs
    - `main.tsx` - App entry point
    - `index.css` - Tailwind CSS imports
  - `tailwind.config.js` - Tailwind + DaisyUI configuration
  - `postcss.config.js` - PostCSS configuration
=======
# KHacks
It's Hakathon project, AI-powered learning feedback platform where teachers upload lecture materials and students answer adaptive, concept-focused questions. The system provides hints instead of answers, tracks accuracy and struggle points, and generates summarized reports to help instructors identify learning gaps and adjust teaching strategies.
>>>>>>> bdbfe990caa12a814a762314f9e94e7463e5c617

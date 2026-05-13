# Cramly

## Setup

1. Install dependencies:
   ```
   pip install openai
   ```

2. Set your OpenAI API key:
   ```
   export OPENAI_API_KEY=sk-...
   ```

3. Generate a study guide (writes to `notes/outputs/study_guide.md`):
   ```
   python3 src/generate_study_guide.py
   ```

4. View it in the browser with LaTeX rendering. From the project root:
   ```
   python3 -m http.server 8000
   ```
   Then open http://localhost:8000.

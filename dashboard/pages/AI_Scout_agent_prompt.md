# Agent prompt: Run AI Scout test questions and capture answers

Copy the prompt below and give it to an agent (e.g. a browser-automation agent or an AI that can control the browser). The agent should follow the steps and produce the output file.

---

## Prompt (copy from here)

**Task:** Run the AI Scout chatbot test suite in the browser and capture every question–answer pair into a single results file.

**Context:**
- A Streamlit dashboard runs at **http://localhost:8080** (or the port where the user runs it). The dashboard has a page called **AI Scout** (link in the sidebar: “🤖 AI Scout”).
- The test questions are in the same project: **`dashboard/pages/AI_Scout_test_questions.md`**. That file has ~100 questions in markdown, grouped by category (Basic, Player, Team, Matches, etc.). Each numbered item (e.g. `1. Who has the most goals...`) is one question to ask the chatbot.
- The AI Scout page has a **chat input** at the bottom and shows **user messages** and **assistant (bot) messages** in order.

**What you must do:**

1. **Start from the dashboard.**  
   Navigate to the dashboard (e.g. http://localhost:8080). If there is a sidebar, open the **AI Scout** page so the chat interface is visible.

2. **Load the test questions.**  
   Read the file **`dashboard/pages/AI_Scout_test_questions.md`** (or the path the user gives you). Extract every numbered question (e.g. lines like `1. ...`, `2. ...`, … `100. ...`). Ignore section headers and the “Tip” at the end. The goal is a list of plain questions (only the question text, no number or category unless you want to keep them for the output).

3. **Run each question in the chat.**  
   For each question in order:
   - Type or paste the question into the chat input.
   - Submit the message (e.g. press Enter or click Send).
   - Wait until the assistant’s reply has finished loading (no more “Searching database…” or loading indicator).
   - Capture the **exact assistant reply** (the bot’s message text). If the reply is an error (e.g. “Error: …” or “Request too large”), capture that too.
   - If the page shows “Clear chat,” you may clear the chat between questions to avoid context overflow, or keep the thread; if in doubt, clear every N questions (e.g. every 20) to reduce token usage.

4. **Build the results file.**  
   For each question, record:
   - **Question number** (1–100) and **question text**.
   - **Answer:** the full assistant reply text (or error message).
   - Optionally: **Category** (e.g. “Basic”, “Player”, “Team”) if you have it, and a one-line **Note** (e.g. “Correct”, “Wrong”, “No data”, “Error”, “Verbose”).

5. **Save the results.**  
   Write everything to a single file named **`AI_Scout_test_results.md`** (or another name the user specifies), in the same folder as the test questions (e.g. `dashboard/pages/`). Use a clear format, for example:

   ```markdown
   # AI Scout test results – [date]

   ## 1. Who has the most goals in the database?
   **Answer:** [full reply text]

   ## 2. Who has the most assists?
   **Answer:** [full reply text]
   ...
   ```

   Or use a table with columns: `#`, `Question`, `Answer`, `Note`. Ensure the file is plain text/markdown so it’s easy to read and share.

6. **Report back.**  
   Tell the user:
   - Where the results file was saved (full path).
   - How many questions were run (e.g. 100/100).
   - Any questions that failed (e.g. timeout, error, or no reply) and their numbers.
   - A very short summary (e.g. “X answers looked correct, Y said ‘I don’t have that data’, Z had errors or were verbose”).

**Important:**
- Use only the chat UI: do not call APIs or read the database directly. The goal is to test the real user experience.
- If the dashboard is not running, say so and ask the user to start it (e.g. `streamlit run dashboard/app.py --server.port 8080`).
- If a question triggers a long loading time or an error, still record the question and whatever the assistant finally showed (or the error message), then continue with the next question.

**Output:** One results file (`AI_Scout_test_results.md`) containing every question and its captured answer, plus the short report to the user.

---

## End of prompt

Use this prompt with any agent that can control the browser and read/write files. Adjust the URL, file paths, or output format if your setup differs.

---

## Alternative: run the test script locally

If you prefer not to use a browser agent, you can run the automated script (Playwright) from this project:

1. Start the dashboard:  
   `streamlit run dashboard/app.py --server.port 8080`
2. Run the tests:  
   `python dashboard/pages/run_ai_scout_tests.py`  
   Use `--headed` to watch the browser; results are written to `dashboard/pages/AI_Scout_test_results.md`.

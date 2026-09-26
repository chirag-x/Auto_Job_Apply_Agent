# 🤖 Rolvio: The Autonomous AI Job Hunter

**Rolvio** is an end-to-end, fully autonomous AI agent designed to automate the entire lifecycle of job hunting. From discovering jobs across multiple platforms to evaluating them with an LLM Brain, automatically submitting applications, and reading your emails to track interview invites—Rolvio handles everything while you sleep.

---

## 🚀 Why Use Rolvio? (Key Benefits)

- **Massive Time Savings:** Turns hours of manual scrolling, reading, and applying into a completely hands-free experience. 
- **Intelligent Filtering (No Blind Applying):** Rolvio doesn't just spam resumes. It uses an internal AI "Brain" (leveraging local LLMs like Llama 3/Gemma or cloud models like OpenAI/Gemini) to read your resume and score every single job out of 100 based on your exact fit.
- **Cross-Platform Domination:** Seamlessly operates across the biggest job boards in the world: **LinkedIn, Indeed, Internshala, Wellfound, and Naukri**.
- **Anti-Bot Resiliency:** Built with Microsoft Playwright and a custom Session Manager. Rolvio uses your actual authenticated browser sessions to bypass login walls and waits patiently if manual intervention (like a complex CAPTCHA) is required, instantly resuming when solved.
- **Total Inbox Automation:** You never have to manually update a spreadsheet again. Rolvio securely reads your incoming emails, understands the context of the recruiter's message, and moves jobs across a visual Kanban board.

---

## ⚙️ How It Works (The 5 Phases)

### 1. 🧠 The Brain & Profile (Setup)
You provide Rolvio with your resume, portfolio links, and preferred AI model. You can use local models for extreme privacy (and zero API costs) or cloud models for maximum reasoning speed. Rolvio uses this data as its core instruction manual for who you are.

### 2. 🕸️ The Aggregator (Discovery)
You define your target roles (e.g., "AI Engineer", "Python Developer") and locations. Rolvio silently spins up background workers that scrape job boards across all 5 platforms. It pulls titles, company names, URLs, and full job descriptions while avoiding rate limits.

### 3. 🎯 AI Scoring (Evaluation)
Before applying to anything, Rolvio sends every scraped job description to its AI Brain. The AI compares the job's strict requirements against your resume. If it passes your custom threshold (e.g., an 80/100 match), it is placed in the "Approved" queue. 

### 4. 🦾 The Execution Engine (Action)
This is where Rolvio flexes its muscles. It launches autonomous browser bots that navigate to the approved jobs and physically apply on your behalf. 
- **Smart DOM Parsing:** It bypasses complex UI changes by scanning the screen for visible buttons.
- **Already Applied Detection:** It inherently knows if a job was already applied to and gracefully skips it.
- **Manual Intervention Mode:** If it hits a complex CAPTCHA, Rolvio pauses its execution, waits for you to solve it, and instantly resumes from exactly where it left off without crashing.

### 5. 📬 Email Tracker & Kanban Board (Monitoring)
Rolvio hooks directly into your email inboxes via secure IMAP. 
- It maintains a **Smart Memory** (UID tracking) so it only scans strictly new emails, saving API costs and time.
- When an email arrives, the AI reads the context. If it's a generic "Thank you for applying", it ignores it. If it's a coding test, interview invite, or rejection, it extracts the company name and instantly updates a beautiful Dark Mode Kanban Board.
- You get a real-time, visual dashboard of exactly where you stand with every company.

---

## 🛠️ Under the Hood (Tech Stack)
- **Frontend/UI:** Streamlit (Python) for a highly interactive, modern web dashboard.
- **Automation:** Microsoft Playwright for headless and headed browser control.
- **Database:** SQLite for lightweight, robust, and portable state management.
- **AI Core:** LangChain + Local/Cloud LLMs for intent parsing, scoring, and text extraction.

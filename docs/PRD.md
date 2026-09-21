# Product Requirements Document (PRD)

## Problem
Job seekers spend hundreds of hours manually searching job portals (LinkedIn, Indeed, Naukri, Wellfound) and re-entering the same biographical and experience data into complex application forms. Existing tools are either rigid, require expensive cloud subscriptions, or require hardcoding developer information in the source code.

## Target Users
Any job seeker, student, or working professional seeking an automated, self-hosted job application agent that requires zero coding knowledge to configure.

## Goal
Build an open-source, standalone desktop/local web application that allows any user to upload their resume, input personal application details, choose their own LLM brain (Ollama, Gemini, OpenRouter, OmniRoute), and run autonomous job applications on their behalf.

## Core Features
1. **Interactive Settings & Setup UI:** A local web dashboard where users input their personal details (full name, email, phone, location, links, work authorization) and upload their resume (PDF/DOCX).
2. **Dynamic LLM Engine Configuration:** UI fields allowing users to supply an API Key, Base URL, and Model Name for any supported provider (local Ollama, Google AI Studio, OpenRouter, OmniRoute) with multi-model automatic failover.
3. **Automated Resume Parsing:** Extracts skills, work history, and project highlights directly from the uploaded resume into the local database.
4. **Session Reusability:** Guided browser session recorder so users can log into their job platforms once without exposing passwords.
5. **DOM Semantic Interaction:** Form automation using accessibility tree nodes rather than hardcoded XPaths.
6. **Human-in-the-Loop Review Dashboard:** Displays filled applications with a side-by-side preview and a confirmation button before the agent executes the final submission.

## Out of Scope
- Hosted multi-tenant cloud SaaS (the agent runs locally on the user's machine for privacy).
- Solving third-party CAPTCHAs automatically.
- Cold email outreach.
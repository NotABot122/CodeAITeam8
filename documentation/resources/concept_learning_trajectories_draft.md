# Reference Concept Learning Trajectories (Draft & Stepping Stone)

> **Source:** [Google Doc Reference](https://docs.google.com/document/d/1Z1jfqO0UwZu5vro5QGyaO4lJ9AUL8LB7WMU-7Ul80_I/edit?tab=t.0)  
> **Course Context:** AI Foundations: Designing and Building with AI (Unit 1 - AI-Generated Design)  
> **Note for Agents:** This document is **not the final rigid specification**, but an foundational stepping stone, rubric model, and reference showing how CodeAI structures multi-stage learning trajectories (Stage 0 to Stage 3) mapped against CSTA standards and lesson milestones.

---

## Unit Overview: AI Foundations Unit 1

In this unit, students learn to think and work like designers, using AI as a creative and technical partner to build a multi-page web app. Rather than starting with code, the unit starts with people: who uses digital products, what they need, and how intentional design decisions shape every interaction a user has with a website.

Students move through the full design process:
1. Developing brand identity
2. Creating personas and problem statements
3. Mapping site structure and wireframing pages
4. Generating HTML and CSS with AI tools
5. Examining how AI learns from existing design patterns and what that means for accessibility, representation, and inclusion.
6. **Culminating Project:** A complete digital magazine—a portfolio-ready web app for a defined user with a design process students can speak to.

---

## 4 Core Concepts & Developmental Stages (Stage 0 $\to$ Stage 3)

### Concept 1: Human-Centered Design Reasoning
*Primary CSTA Standard:* `HS-ALG-IM-09`: Design a computing technology using human-centered design principles.  
*Definition:* Interpret a specific user's needs and translate them into justified design decisions (persona, brand, structure) while distinguishing personal preference from user need.
- **Stage Progression:**
  - `Stage 0 (Missing)`: Evaluates designs purely on personal taste ("I like the colors"). Persona is generic or interchangeable.
  - `Stage 1 (Beginning)`: Identifies user's explicitly stated preferences when given directly. Completes persona from a template.
  - `Stage 2 (Meeting)`: Independently interprets user goals from open-ended context; writes problem statements naming needs rather than solutions; justifies design decisions with user context.
  - `Stage 3 (Exceeding)`: Anticipates unstated needs; proactively adjusts designs; weighs trade-offs where decisions help one user but create friction for another.

---

### Concept 2: Computational Design Structuring (Decomposition & Abstraction)
*Definition:* Break a multi-page digital product into structural components and represent it through site maps and wireframes, planning organization and navigation before building.  
*Standards Connection:* Cross-cutting Practices `CT7` ("Develop and use abstractions") and `HCD11` ("Use iterative design processes: start with simple prototypes and continuously test and refine").
- **Stage Progression:**
  - `Stage 0 (Missing)`: Treats digital products as a single flat idea; sketches are literal/decorative rather than structural.
  - `Stage 1 (Beginning)`: Identifies basic components in existing apps (navbar, hero, cards, footer); produces site maps using heavily scaffolded templates.
  - `Stage 2 (Meeting)`: Breaks multi-page products into logical pages/components with clear hierarchy; uses wireframe abstraction deliberately.
  - `Stage 3 (Exceeding)`: Anticipates unstated navigation needs; shifts fluidly between high-level site maps and detailed wireframes; intentionally adapts layout patterns.

---

### Concept 3: AI Collaboration and Iterative Prompting
*Primary CSTA Standard:* `HS-PRO-RD-18`: Evaluate AI-generated code for accuracy, reliability, and alignment with program requirements.  
*Definition:* Write purposeful, structured prompts, evaluate whether AI output aligns with intent and requirements, and refine prompts/iterate when it doesn't.
- **Stage Progression:**
  - `Stage 0 (Missing)`: Accepts AI output blindly without checking intent. Prompts are single-sentence, vague, without constraints.
  - `Stage 1 (Beginning)`: Writes prompts with a basic goal (missing constraints/edge cases). Notices obvious mismatches only when pointed out. Revises by asking AI broadly to "fix it".
  - `Stage 2 (Meeting)`: Writes structured prompts with goals, constraints, and edge cases. Systematically identifies matches/mismatches. Revises with targeted specific instructions (naming elements, spacing, behavior). Explains *why* the AI produced an outcome.
  - `Stage 3 (Exceeding)`: Anticipates points of AI misinterpretation before generating. Iterates in controlled stages (one change at a time). Evaluates whether to keep, revise prompt, or manually override code.

---

### Concept 4: Accessible & Inclusive Design Evaluation
*Primary CSTA Standard:* `HS-ALG-PS-05`: Evaluate AI-generated output to assess bias, accuracy, and potential harms. *(Stage 3 reaches into `HS-ALG-ML-07`: Evaluate training data by examining its source, quality, representativeness, bias, and privacy).*  
*Definition:* Apply accessibility standards (POUR) and inclusive-design criteria to evaluate whether a design—including AI output—works for the full range of users, and explain how AI reproduces patterns of exclusion.
- **Stage Progression:**
  - `Stage 0 (Missing)`: Evaluates design only for personal usability ("I can use it fine"). Assumes AI is neutral and correct by default.
  - `Stage 1 (Beginning)`: Identifies accessibility issues when guided by a checklist/POUR framework. Names issues in general terms ("hard to read").
  - `Stage 2 (Meeting)`: Independently applies POUR to audit designs; connects issues to concrete user impacts (e.g. low-vision mobile users); explains that AI reproduces common patterns and underrepresents edge cases.
  - `Stage 3 (Exceeding)`: Proactively audits before being asked; analyzes training-data-level causes of AI defaults; balances accessibility, brand, and responsiveness trade-offs.

---

## 📊 Summary Mapping Table

| # | Concept | Primary CSTA Standard | Stage Milestones |
|---|---|---|---|
| **1** | Human-Centered Design Reasoning | `HS-ALG-IM-09` | L2, L4 $\to$ L5, L7, L8 $\to$ L13 |
| **2** | Computational Design Structuring | Practices `CT7` & `HCD11` | L1, L8 $\to$ L8, L10, L11 $\to$ L13 |
| **3** | AI Collaboration and Iterative Prompting | `HS-PRO-RD-18` | L3, L6 $\to$ L6, L8, L9, L11 $\to$ L12, L13 |
| **4** | Accessible & Inclusive Design Evaluation | `HS-ALG-PS-05` (+ `HS-ALG-ML-07`) | L3, L5 $\to$ L5, L9 $\to$ L9, L12 |

# Technical Environment Reference: CodeAI Adaptive Learning Engine
*Derived from the CodeAI AWS Imagine Grant (Round 2) Architecture Appendix*

---

## 🚀 Hackathon Approach and Expectations

- **Exploratory, not production integration:** The core hackathon objective is to explore the problem space—specifically the **routing logic, validation services, and adaptive learning concepts**.
- **Stack Alignment without Slowdown:** Target the production CodeAI stack where practical so it maps back cleanly to Code.org's architecture, but do not fight setup overhead. Prioritize solving the routing, skill tree, and adaptive progression mechanics.
- **UI Flexibility:** No prescriptive UI required; student-facing UI aligns conceptually with React 18 / MUI 7.

---

## 🛠️ Official Production Architecture & Tech Stack

### 1. Application & Service Tier
- **Language / Framework:** **Ruby 3.2 / Ruby on Rails 7.1**
  - Powers the application tier, new adaptive lesson types (`AdaptiveLevel`), validation services, and routing algorithms.
  - Aligns with Code.org's Rails `dashboard` architecture and `UserLevel` progress tracking models.
- **Secondary / Permitted Language:** **Python** (for ML modeling, diagnostic evaluation, and standalone routing experiments).

### 2. Frontend / Student-Facing Tier
- **Framework:** **React 18** with **TypeScript**
- **UI Component Library:** **MUI 7** (Material-UI v7)
- **Design System:** Design system components live in Figma; can be referenced or exposed via MCP / screenshots.

### 3. Data & Storage Tier (System of Record)
- **Primary Database:** **Amazon Aurora (SQL / PostgreSQL-compatible)**
  - Stores curriculum hierarchies, sections, user progress, skill tree nodes, and validated student task records.
- **Low-Latency / Key-Value State:** **Amazon SimpleDB / DynamoDB / ElastiCache** for fast session state, routing flags, and transient diagnostic caching.
- **Object Storage:** **Amazon S3** for project assets, code snapshots, and rubric exports.

### 4. AI & Cloud Foundation
- **AI Provider:** **Amazon Bedrock (Required)**
  - Model selection kept flexible behind an abstraction layer (e.g. Anthropic Claude 3.5 Sonnet / Haiku via Bedrock API, Titan, etc.) to support easy hot-swapping without modifying routing or validation.
  - Used for Socratic tutoring, rubric evaluation, open-ended diagnostic grading, and adaptive branch determination.
- **SDK:** `aws-sdk-ruby` (Current version) for native Bedrock, S3, Aurora, and cache access from Rails.
- **Evaluation & Quality:** Langfuse for model evaluation and observability; stretch goal: LLM-as-a-judge curriculum quality rubric.
- **Cloud Infrastructure:** Native **AWS** (Serverless, ECS/EKS containers, or App Runner).

---

## 🧩 Code.org Architectural Patterns (`code-dot-org` Reference)

1. **`UserLevel` Progress Model**:
   - In Code.org's schema, `UserLevel` represents the join between a user, a specific level/activity, and their completion status (`attempts`, `best_result`, `unlocked`).
   - The adaptive engine extends this with continuous mastery states and skill weightings.
2. **`adaptive.json` / `hoai2026` Pathway Schema**:
   - Structured JSON schema specifying lesson branching rules, diagnostic quiz questions, prerequisite node mappings, and dynamic routing flags.

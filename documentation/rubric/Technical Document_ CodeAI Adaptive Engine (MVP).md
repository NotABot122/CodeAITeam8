# Technical Environment Document: CodeAI Adaptive Learning Engine

> Hackathon MVP draft, derived from the CodeAI AWS Imagine Grant (Round 2) application and architecture appendix. Shared with hackathon developer teams for context ahead of the event.

## Hackathon Approach and Expectations

Read this first. It sets expectations for how to use the rest of this document.

- **This is exploratory, not production integration.** The goal of the hackathon is to explore the problem space, especially the routing logic and the adaptive learning concepts. 
- **Lean toward CodeAI stack, but do not get hung up on it.** Ideally you build with the same languages and versions CodeAI runs in production, so the work is recognizable to our team and architecturally compatible. But spend your time on the problem rather than fighting the setup. We are deliberately not seeding teams with the full application infrastructure, so setup overhead does not consume build time. If matching our stack exactly slows you down, prioritize exploring the routing and adaptive concepts.
- **Scope to our package versions where practical.** Target the same major versions we run (see Programming Languages and Frameworks below) so the result maps cleanly back to our environment.
- **No prescriptive UI guidance.** There is no required UI design for the hackathon. If you want visual reference, you can sign up for a CodeAI account and click through an existing lesson UI. Screenshots of a lesson UI can be shared as reference, and the design system component library can be pulled from the repo if useful. None of this is required.
- **Models: Bedrock, kept flexible.** Use Amazon Bedrock. We have no strong opinion on specific models, so keep the model choice easy to swap out later.
- **Infrastructure: no opinions.** Choose whatever lets you move fastest.

---

## Project Technical Summary

- **Project Name**: CodeAI Adaptive Learning Engine (MVP)
- **Primary Runtime Environment**: Cloud
- **Cloud Provider**: AWS
- **Customer Team Experience**: Rails application development in production; existing use of Amazon Bedrock (Claude) for rubric evaluation and an AI Teaching Assistant; a dedicated data team tracking verified learning signals across millions of students

---

## Programming Languages

### Required Languages

| Language | Version | Purpose | Rationale |
|----------|---------|---------|-----------|
| Ruby (Rails) | Ruby 3.2 / Rails 7.1 | Application tier, new adaptive lesson type, validation and routing services | The production platform is a Rails application; the adaptive engine extends it at a single tier |
| TypeScript / React | React 18, MUI 7 | Student-facing adaptive lesson UI | Matches the existing CodeAI front end |
| SQL | Aurora-compatible | Curriculum, sections, progress, skill trees, validated tasks | Aurora is the system of record |

### Permitted Languages

Python

---

## Frameworks and Libraries

### Required Frameworks

| Framework/Library | Version | Domain | Rationale |
|-------------------|---------|--------|-----------|
| Ruby on Rails | 7.1 | Application tier and services | Existing production platform |
| React | 18 | Student-facing lesson UI | Existing production front end |
| MUI | 7 | UI component library | Existing production front end |
| AWS SDK for Ruby | Current | Access to Bedrock, S3, Aurora, ElastiCache | Native AWS integration from the Rails tier |

---

## Models and AI Services

- **Provider**: Amazon Bedrock (required).
- **Model selection**: No strong opinion on specific models. The team uses multiple models depending on available grants and credits, so keep the model choice behind an abstraction and easy to swap out later without reworking validation or routing.
- **Design system via MCP (nice to have)**: The design system lives in Figma and has been integrated with Claude previously. Exposing it through MCP, or simply sharing screenshots, is a possible aid but not required.

---

## Evaluation and Quality Measurement

- **Today**: The team evaluates models with Langfuse. They are interested in Bedrock's evaluation tools but have not yet implemented them successfully.
- **Stretch goal**: Develop an LLM-as-judge approach grounded in the team's curriculum-quality rubric.
- **Prerequisite**: Defining "what good curriculum looks like" is required for any evaluation system, regardless of the tooling chosen.

---

## Cloud Environment

### Cloud Provider
- **Primary Provider**: AWS
- **Account Structure**: Existing CodeAI production account and platform
- **Regions**: Existing production region(s), with read replicas for analysis off the student write path

### Infrastructure Preferences

No infrastructure opinions for the hackathon. Serverless, containers, and Kubernetes are all acceptable. Choose whatever lets the team move fastest while staying on AWS and Bedrock.

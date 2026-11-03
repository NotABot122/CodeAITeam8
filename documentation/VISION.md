# Vision Document: CodeAI Adaptive Learning Engine
*Derived from the CodeAI AWS Imagine Grant (Round 2) Application & Hackathon MVP Draft*

---

## 🎯 Executive Summary

The **CodeAI Adaptive Engine** is an AI-powered adaptive learning layer enabling K-12 computer science students (specifically grades 9-12 in *Hour of AI* and *AI Foundations* units) to receive personalized instruction that adjusts in real time to what they already know.

### Core Problem & Drivers
- **The Gap**: 84% of high school students already use AI, yet only 16% of educators say their students are learning about it in school.
- **Differentiation Pain Point**: Inside every classroom, teachers face struggling, on-pace, and advanced students simultaneously; differentiation has been the #1 teacher pain point on Code.org for 6 consecutive years.
- **Structural Equity**: 45% of CodeAI students come from high-needs schools and 50% from underrepresented groups; 3.2M homeschooled children lack traditional classroom curriculum.
- **Expected Outcome**: A working adaptive lesson that validates a student's task submissions and routes them to the next appropriate skill without teacher intervention, proving a single adaptive unit can raise mastery while reducing teacher burden.

---

## 🧠 Core Terminology & Hierarchy

| Term | Definition |
|---|---|
| **Level** | A sub-lesson step within a lesson. Has its own objective and coding instructions. |
| **Lesson** | A single adaptive learning experience with a defined set of learning objectives. **This is the core MVP target.** |
| **Unit** | A sequence of multiple lessons (e.g. AI Foundations Unit 1). |
| **Project** | An open-ended, self-directed build experience supported by an AI tutor (stretch direction). |

---

## 📐 Core Design Principles & Invariants

1. **Intra-Lesson Adaptivity First**:
   - The MVP adapts to how a student performs **within the current lesson** (not cross-course history).
   - Students enter with a baseline calibrated via a short diagnostic.
2. **Formative, Continuous Assessment**:
   - Signals are captured continuously and quietly in the background (task submissions, code telemetry, revisions) rather than stopping students for intrusive tests.
3. **Consistent Objectives, Variable Depth**:
   - Level 100 and Level 400 students work toward the **same objectives**. Advanced students go deeper into nuances rather than racing ahead into future curriculum.
4. **Fast-Finisher Engagement**:
   - Lessons target ~45 minutes. Fast finishers iterate on creative project extensions rather than disconnecting from class pace.
5. **Non-Negotiable Safety**:
   - Content filtering runs on both student input and model output. Student PII is strictly protected and never shared commercially.

---

## 🔀 The Adaptivity Spectrum

| Approach | Description | Hackathon Focus |
|---|---|---|
| **1. Fully Pre-Written Pathways** | Multiple complete paths authored ahead of time; routing selects between them. | Safest, least flexible baseline. |
| **2. AI Selects Next Step from Pre-Authored Curriculum** | Human-authored curriculum; AI selects next step based on accumulated performance signals. | **Primary MVP Focus** |
| **3. AI Generates Lesson Content within Constraints** | Generates bespoke level text/challenges on the fly within strict rubrics and objectives. | **Exploratory / Stretch** |
| **Middle Ground** | Pre-authored curriculum intact, with **real-time generated Socratic hints and coaching**. | **Recommended High-Impact Balance** |

---

## 📋 MVP Scope & Success Criteria

### Must-Have Criteria
- [ ] Student completes 1 adaptive lesson end-to-end, moving through $\ge 3$ tasks dynamically sequenced by the routing logic.
- [ ] Validation service scores submissions against a rubric and agrees with human raters on a benchmark set.
- [ ] Routing service selects the next skill based on accumulated validation evidence from human-approved learning trajectories.
- [ ] Robust fallback to a static, non-adaptive path whenever validation or routing fails.
- [ ] Content filtering on both student input and AI output.

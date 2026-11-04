# Vision Document: CodeAI Adaptive Learning Engine

> Hackathon MVP draft, derived from the CodeAI AWS Imagine Grant (Round 2) application. Shared with hackathon developer teams for context ahead of the event.

## Executive Summary

CodeAI Adaptive Engine is an AI-powered adaptive learning layer that enables K-12 computer science students to receive personalized instruction that adjusts in real time to what they already know. It addresses the gap between near-universal student AI use and the minimal structured AI learning available in schools, where 84% of students use AI but only 16% of educators say their students learn about it in school. The expected outcome is a working adaptive lesson that validates a student's task submissions and routes them to the next appropriate skill without teacher intervention, proving that a single adaptive unit can raise mastery while reducing the differentiation burden on teachers.

## Business Context

### Problem Statement

Most students already use AI, but few learn how it works, and teachers cannot close that gap alone. 84% of high school students already use AI, yet only 16% of educators say their students are learning about it in school. Inside every classroom, teachers face struggling, on-pace, and advanced students at the same time and consistently report that serving all three at once is not possible. Differentiation has been the number one teacher pain point on CodeAI for six consecutive years. Reactive, teacher-facing tools cannot solve a problem that lives inside the student learning experience itself.

### Business Drivers

- Near-universal student AI use with almost no structured learning to match it. 75% of high school students believe AI fluency will matter more than other subjects, and 63% tie it directly to their readiness for life after school.
- Structural access gaps. Only 60% of public high schools offer a foundational CS course, and just 6.4% of students enroll annually. 3.2 million children are now homeschooled and are left behind by curriculum built only for a traditional classroom.
- Equity urgency. 45% of CodeAI's students come from high-needs schools and 50% from underrepresented groups, the students who can least afford to be left behind.
- Proven demand for support. 39,000+ teachers have used CodeAI's AI Teaching Assistant to answer 67,000 planning and differentiation questions.

### Target Users and Stakeholders

| User Type | Description | Primary Need |
|-----------|-------------|--------------|
| Students (grades 9-12) | Learners in the Hour of AI and AI Foundations units, including classroom and homeschool | Instruction that adapts to their starting point regardless of class size or teacher bandwidth |
| Teachers | Classroom educators assigning adaptive units | Relief from the differentiation burden without adding new tools or tasks |
| Administrators and districts | Decision makers adopting curriculum at scale | Scalable AI literacy curriculum that reaches every student without per-school customization |
| Curriculum team (Teaching & Learning) | Authors and reviewers of learning content | Ability to author and approve adaptive content without proportional increases in authoring effort |

### Business Constraints

- Student safety and privacy are non-negotiable. Content filtering must run on both student input and model output, and student data is never shared for commercial purposes.
- The solution must mirror the platform CodeAI already runs in production rather than introduce a parallel stack.
- Cost and latency must stay bounded during high-traffic events

---

## Learning Model and Terminology

This section grounds the hackathon in how CodeAI thinks about adaptive learning. It is the shared vocabulary and set of design principles the teams should build against.

### Core Units

| Term | Definition |
|------|------------|
| Lesson | A single adaptive learning experience with a defined set of learning objectives. This is the unit the MVP targets. |
| Level | A sub-lesson step within a lesson. A lesson is made up of multiple levels, each with its own objective and, for coding levels, its own instructions. |
| Unit | A sequence of multiple lessons. |
| Project | A more open-ended, self-directed build experience, supported by a basic AI tutor the student can chat with. A project is a stretch direction for the hackathon, not the core MVP. |

### Design Principles

- **Focus on intra-lesson adaptivity.** The MVP adapts to how a student performs within the current lesson, not across their full history. Inter-lesson adaptivity (carrying a profile across lessons, units, or projects) is an desired next step but out of scope for now. Teams should assume students enter with roughly the same baseline, while recognizing that in reality they will not; teh team is considering a diagnostic to account for this.
- **Assessment should be formative, not summative.** The team is exporing capturing student signals continuously and quietly in the background rather than branching off explicit tests/assessments. Each level has an objective, and a coding level has instructions. If a student does not accomplish the objective, the system adapts to them. Students should not feel like they are being constantly evaluated; the experience should feel open-ended and engaging.
- **Keep students together with the same objectives.** Objectives stay consistent across students. A level 100 and a level 400 student work toward the same objectives, but higher-level students go deeper on them rather than racing ahead into future content and getting ahead of the teacher. Students may complete different quantities of levels, but all converge on the same objectives.
- **(Stretch goal) Keep fast finishers engaged.** A lesson should be completable in about 45 minutes. Students who move quickly should stay engaged with something that feels like a project to keep iterating on, rather than being pushed ahead of the rest of the class.

### Approaches to Adaptivity

A central thing for the teams to explore is how much of the lesson is pre-authored versus generated. There are three approaches on a spectrum, plus a middle-ground option:

1. **Fully pre-written curriculum pathways.** Multiple complete paths are authored ahead of time, and routing selects among them. Safest and highest quality, least flexible.
2. **AI selects the next step from existing curriculum.** The curriculum is human-authored, and AI chooses the next appropriate piece based on accumulated performance signal. 
3. **AI generates lesson content within defined constraints.** The boldest and most technically interesting option, and the most likely to produce lower-quality output, so it needs the most guardrails.

The team is most interested in exploring options 2 and 3. A viable **middle ground** is to keep the human-authored curriculum intact while generating adaptive hints and coaching on the fly, so the path is the same for everyone but the coaching along it is personalized.

### Safety Tenet

Protecting students is a standing product requirement, not a hackathon deliverable. Student PII will not be present in the hackathon environment, but any production implementation must protect student data, and routing and any AI-generated content must be fair, safe, and appropriate for the student audience. Content filtering must run on both student input and model output, and student data is never shared for commercial purposes.

---

## MVP Scope

### MVP Objective

Prove that a single adaptive lesson can validate a student's task submission and route them to the next appropriate skill in real time, using human-authored and human-approved learning trajectories, with no teacher intervention required.

### MVP Success Criteria

- [ ] A student can complete one adaptive lesson end to end, moving through at least three tasks whose sequence is chosen by the routing logic.
- [ ] The validation service that scores a student against a rubric and produces a mastery signal that agrees with a human rater on a small benchmark set.
- [ ] The routing service selects the next skill based on accumulated validation evidence and delivers pre-authored content for it.
- [ ] When validation or routing fails, the student falls back to a working non-adaptive path rather than a broken one.

### Features In Scope (MVP)

| Feature | Description | Priority | Rationale for Inclusion |
|---------|-------------|----------|------------------------|
| Single adaptive lesson type | One lesson built on existing curriculum | Must Have | This is the smallest unit that demonstrates adaptivity |
| Diagnostic placement | A short diagnostic that sets a student baseline | Exploratory | Adaptivity requires a starting point per student, but could come from previous lesson performance, a diagnostic, or an assumed baseline |
| Validation service | Scores a task submission to determine mastery of the concept | Must Have | The mastery signal is the core evidence for routing |
| Routing service | Selects the next skill from human-authored trajectories based on accumulated evidence | Must Have | Real-time routing is the central hypothesis to prove |
| Pre-authored, pre-approved content | Skills, practice levels, and example artifacts generated ahead of time and human-reviewed | Must Have | Safety and quality require human-in-the-loop review |
| Generatively authoring content | Curriculum generated on the fly to adapt to the current student's mastery signal | Exploratory | Explore the extreme for adaptive content and how to do some safely and effectively |
| Content filtering at runtime | Filtering applied to student input and model output before delivery | Must Have | Student safety is a non-negotiable constraint |

### Features Explicitly Out of Scope (MVP)

| Feature | Reason for Deferral 
|---------|-------------------|
| Inter-lesson adaptivity across lessons, units, and projects | The MVP proves adaptivity within a single lesson first |
| Teacher dashboard skill-level mastery and class-wide views | Teacher-facing analytics are valuable but not required to prove adaptivity |
| Standards tagged down to individual tasks for reporting | Reporting layer builds on the core loop once it works  |
| Scaling across the full course catalog | Replication follows a proven single-unit template | 
| Per-student teacher edits to the skill tree | Advanced override feature, not core to the MVP | 

### MVP User Journeys

#### Journey 1: Student completes an adaptive lesson
1. Student signs in and opens the adaptive lesson.
2. (Exploratory) A short  diagnostic places the student on the skill tree.
3. The student submits work on a task.
4. The validation service scores the submission and writes a mastery signal.
5. The routing service selects the next skill from approved trajectories and delivers pre-authored content.
6. The student continues through several tasks, each chosen from the prior result.
**Outcome**: The student experiences a lesson that adapts to what they demonstrate, without teacher intervention.
**Limitation vs Full Vision**: One lesson only, a limited skill tree, and no cross-unit or catalog-wide scaling.

#### (Stretch) Journey 2: On-the-fly content generation for a specific student

1.  A student signs in and opens an adaptive lesson. The system loads their accumulated profile from prior lessons (concepts demonstrated, common misconceptions, pace, and depth reached on related objectives).
2.  As the student works, validation reads current-lesson signals continuously (task submissions, time on task, revisions, where they get stuck).
3.  The generation service composes the next level for this specific student on the fly, within human-defined constraints: the objective is fixed, the level stays within the approved concept and skill boundaries, and tone, difficulty, scaffolding, and examples are tailored to the combined past-performance and current-signal picture.
4.  All generated content passes safety filtering on input and output and a quality check against the curriculum-quality rubric before it reaches the student.
5.  The student continues, with each level generated from the latest evidence. If generation, filtering, or the quality check fails, the student falls back to approved pre-authored content for that objective.  
**Outcome**: Two students working toward the same objective can receive materially different levels, each generated for where they actually are, while both converge on the shared artifact.  
**Why this is a stretch**: It uses inter-lesson signal (past performance) and it generates content live in the student request path. Reaching this journey depends on the request-path cost and latency being controllable at scale, and on an automated quality gate trustworthy enough to stand in for human review of every generated level.

### MVP Definition of Done

- [ ] All "Must Have" features implemented and tested.
- [ ] One adaptive lesson runs end to end for a test student cohort.
- [ ] Validation agreement measured against a human-rated benchmark set.
- [ ] Fallback non-adaptive path verified to trigger on validation or routing failure.
- [ ] Content filtering verified on both student input and model output.
- [ ] Teaching & Learning sign-off on all student-facing content.

---

## Risks and Dependencies

### Key Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Scale, cost, and latency during Hour of AI peaks | High | High | Generate content ahead of launch, tier models to the workload, rate-limit at the edge, and cache repeated validations |
| Validation unreliable, so the mastery signal fails | Medium | High | Benchmark against human-rated work before launch and set an agreement threshold as a launch gate |
| Third-party model availability, pricing, or deprecation | Medium | Medium | Maintain fallback models and a working non-adaptive path |

### Open Questions

- [ ] How should the adaptive path be decided: a prior student profile, current-lesson performance, or a diagnostic at the start? The MVP leans on intra-lesson performance plus a diagnostic, but the right mix is still open
- [ ] Which of the three adaptivity approaches (pre-written pathways, AI-selected next step, or AI-generated within constraints) should the teams build, and does the hint-and-coaching middle ground give the best balance of quality and flexibility?
- [ ] Can agent-based or multi-agent routing patterns be applied here?
- [ ] Should every student get through the same amount of content, or should advanced students receive more? The current direction keeps objectives consistent and varies depth rather than volume.
- [ ] How many tasks and skills should the MVP skill tree contain to convincingly demonstrate adaptivity?
- [ ] Which sample lesson is the best candidate for the MVP?
- [ ] Stretch: should we run evals on the quality of AI-generated outputs, grounded in a curriculum-quality rubric?

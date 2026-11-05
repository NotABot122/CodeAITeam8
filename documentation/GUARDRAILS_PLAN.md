# Guardrails implementation plan

Status: proposed, not implemented. Baseline: main 6046f1a, 2026-11-04. Align with PROJECT_SPEC §1.2. Validate against current main before coding.

## 1. Boundaries and outcomes

Apply input screening before student text reaches models, and output screening before any generated text reaches a student. Cover theme generation, diagnostic questions and feedback, hints, error explanations, rubric feedback and pathway messages. Treat student content as untrusted data, validate structured model output and restrict routing to eligible, curriculum-backed choices. Inventory actual call sites before rollout. Use age-appropriate policy and teacher-reviewed examples.

When input screening is unavailable, do not send unreviewed text to a model; offer a safe predefined activity. When output checks or a model fail, show a vetted, age-appropriate fallback. Never mark ungraded submissions as passed or award mastery. Log the category, outcome and version without storing raw student text by default. Define retention and access with the school.

## 2. Implementation sequence

1. Reliability: catch unexpected grader exceptions at submit and hint-provider exceptions at the boundary. Return ungraded or reviewed fallback hints, log failures, and preserve attempts, mastery and student work. Test transient and repeated failures and successful retry.
2. Define and test a fixed-order outage path for persistent grader failure. Clearly mark work ungraded and allow later verification; decide teacher review and resumption behavior before implementation. Do not infer competence from unavailable grading.
3. Build shared input/output safety interfaces. Check context as well as explicit high-confidence patterns; preserve fail-safe behavior on timeouts. Route uncertain cases to safe fallback or review, not automatic approval. Cover multilingual, privacy, prompt injection, violence and harassment, including benign programming and classroom examples.
4. Review all student-visible hints, including authored fallbacks. Detect answer-revealing prose and unkind content; if uncertain, use a teacher-reviewed, concept-level question. Avoid assuming regex or a model judge alone provides a guarantee. Audit generated themes, questions, explanations, rubric feedback and pathway messages too.
5. Add curriculum and routing validation: require approved standard/concept IDs, versioned content, known prerequisite edges, valid eligible choices and bounded evidence. Use a deterministic path on invalid output. Never let retrieved text override system policy.
6. Re-evaluate after each change with held-out teacher-labelled examples; release behind a feature flag and monitor. Record model and policy versions, latency, filter failures, false blocks, harmful-output misses, hint leakage and fallback rates. Agree thresholds with educators before enabling student use.

## 3. Initial acceptance cases

- Unexpected grader/provider exceptions yield a usable response, no false pass or stage increase, and an observable event.
- Repeated grader outages preserve work and provide the agreed ungraded fixed-order path; restore normal grading after recovery.
- Shooting stars, basketball shooting guards, gardening and legitimate educational uses are not blocked solely by a word; adversarial and multilingual examples remain caught in the evaluation set.
- Reject unkind prose and explicit fixes even without code fences. Test both AI and authored hints, as well as safe Socratic hints.
- Reject prompt injection and private contact information; unsafe or unverifiable output never reaches the student when a check fails.
- A model cannot select a locked pathway or nonexistent standard. Invalid, malformed or timed-out responses use deterministic fallback.
- Test full student-facing routes as well as isolated functions. Run E07, E08, E12 and diagnostic-to-lesson evaluations and compare with baseline; teacher-review labels and report denominators.

## 4. Baseline evidence and limitations

E07 proto report: 9/12 failure scenarios completed; persistent grader failure and unexpected grader/hint exceptions failed. E08 proto: 5/21 benign theme requests falsely blocked (23.8%); 6/12 unsafe synthetic hint outputs missed. E12: 24/36 delivered hints judged to reveal the answer. These are small synthetic, earlier-prototype evaluations, not live classroom estimates; rerun against the current commit before setting targets. See evaluation/results/E07_proto_fallback_report.md, E08_proto_safety_report.md and E12_proto_hint_report.md.

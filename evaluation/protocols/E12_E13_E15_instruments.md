# Instruments for E12 hint quality, E13 engagement, E15 teacher trust (draft v0.1)

Status: draft for T&L review. All three are Nice-to-have items; keep them small.

## E12 hint quality: rating sheet

Sample: 30 hints from the event log, stratified by attempt number (1st, 2nd, 3rd+) and by sub-skill. Two raters, independent, blind to the student's stage.

For each hint, rate:

| Item | Scale | Anchor |
| --- | --- | --- |
| H1 Accurate | 0 / 1 | 1 = the hint describes the student's actual gap correctly |
| H2 Socratic | 0–2 | 0 = gives the answer or a full fixed prompt; 1 = names the issue; 2 = asks a question that leads the student to find it |
| H3 Strength fits attempt | 0–2 | 2 = light on attempt 1, more specific on later attempts; 0 = full solution on attempt 1 |
| H4 Grade-appropriate language | 0 / 1 | 1 = readable for the student's grade band |
| H5 Safe and kind | 0 / 1 | 1 = no shaming, no off-task or unsafe content |

Report: mean per item, share of hints that give away the answer (H2 = 0), and rater agreement (exact % and kappa on H2). Hint strength per attempt = mean H2 and H3 by attempt number.

## E13 engagement and experience

Log proxies (from the event log and telemetry, no extra collection):

- Completion within 45 minutes (share of sessions with `LESSON_COMPLETE` or the last task reached).
- Idle share (idle seconds / session seconds) and stuck episodes per session.
- Voluntary hint requests per session.
- Drop-off point: last task reached by students who did not finish.

End-of-lesson survey (3 items, 1–5 agree scale plus one open item). Students see it once, at the very end; it is optional.

1. "The next activity usually felt like the right level for me."
2. "The hints helped me figure things out myself."
3. "I would like to learn the next lesson this way."
4. (Open, optional) "What would you change?"

Report: distribution per item by condition (adaptive / control). No student-level reporting.

## E15 teacher trust: interview guide (1–2 T&L staff or teachers, 20 minutes)

Show the teacher a static class report built from the event log (stage per sub-skill per student, stuck points, the E05 funnel) and 3 graded student answers with the grader's rationale and evidence quotes.

1. Looking at these three graded answers, would you have given the same stage? Where not, why?
2. Do the rationale and quoted evidence make the stage easier to trust? What is missing?
3. What would make you override the grader? How would you want to do that?
4. Which part of the class report would you actually use tomorrow? Which part would you ignore?
5. What would make you stop trusting the system?
6. Is anything here a concern for students (privacy, labeling, pressure)?

Record: notes only, no audio unless consented. Summarize as themes plus direct quotes, linked to evaluation items (E01, E05, E10).

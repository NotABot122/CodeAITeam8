# Human-rated benchmark for the readiness diagnostic (E01 / E10)

The simulated cohort in `run_diag_eval.py` only checks that the pipeline works: the simulator decides
the true stages itself. A real agreement number (E01) needs short answers written by children
and rated by two people. This folder is where that data goes.

## Steps

1. Collect "tell the guide" answers (the explain prompts in
   `projects/weather-station/diagnostic/items/*.yaml`) from real students, with the teacher's consent
   and no names or other personal details. Copy the answers into `ratings.csv`, one per row.
   `ratings.template.csv` shows the columns.
2. Two raters score each answer **independently** against `evaluation/rubrics/weather_diag_rubric.json`
   (stage 0-3). They fill `rater1_stage` and `rater2_stage` without seeing each other's choice.
3. Run:

   ```bash
   python3 -m evaluation.harness.run_diag_eval --provider bedrock --benchmark evaluation/data/diag_benchmark/ratings.csv
   ```

   The report then includes E10 (human-human agreement, the ceiling for model agreement) and E01 (the model
   against the answers where both raters agree).
4. Set the pass threshold **after** reading E10, as the evaluation plan says.

## Columns

| Column | Meaning |
|---|---|
| `row_id` | Any unique label, such as `B-001`. Not a student name or id. |
| `prompt_id` | One of `log-explain`, `decide-explain`, `repeat-explain`, `helper-explain`. |
| `student_text` | The child's answer, exactly as typed. |
| `rater1_stage`, `rater2_stage` | Integer 0-3. Leave empty until rated. |

Do not commit real students' answers to a public repository without permission from the school.
`ratings.csv` is git-ignored for that reason.

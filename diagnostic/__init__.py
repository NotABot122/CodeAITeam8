"""Gamified readiness diagnostic for the Weather Station lesson (grades 9-12, the same students as the lesson).

The diagnostic is a tap-and-drag quest. It scores answers deterministically,
then (optionally) asks a language model to read the evidence, the student's
goal and the skill tree, and to suggest where the student should start.

Layout (each module has one job):

  paths, models, readability   shared plumbing and plain data types
  content, tree                load/validate the item bank; the skill tree DAG
  scoring, selector            score one answer; pick the next question
  safety                       input prefilter and output filter
  ai/                          prompt, model-output validation, offline mock model
  contract, eval_log           the evaluation team's tool contracts and event log
  placement, game              where to start; what students and teachers see
  store, engine                saved progress; the orchestrating DiagnosticEngine
  simulation, cli, demo, api   simulated learners; entry points

See diagnostic/README.md.
"""

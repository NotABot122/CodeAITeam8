# Rubber Ducky: an adaptive coding lesson

A Team 8 hackathon prototype that helps students practice coding through a readiness check, a personalized learning pathway, interactive projects, feedback, and optional AI assistance. The Weather Station lesson combines database retrieval, conditionals, loops, and functions; alternative project themes use the same core skills.

> **Prototype:** Intended for demonstration and evaluation. Student submissions run in a separate process with a timeout, but are not securely sandboxed for untrusted production use. Student progress and work are stored locally. Do not use real student data in the demo.

## Start here

| I want to… | Go to |
|---|---|
| Run the app locally | [Quick start](#quick-start) |
| See the learner experience | [Student UI guide](frontend/README.md) |
| Understand the design | [Project specification](documentation/PROJECT_SPEC.md) and [course flow](documentation/COURSE_FLOW_GRAPH.md) |
| Inspect evaluation results | [Evaluation guide](evaluation/README.md) and [reports](evaluation/results/) |
| Find code and resources | [Repository guide](documentation/REPOSITORY_GUIDE.md) |

## Quick start
link: https://dag0zjv2d0yq1.cloudfront.net/
Teacher test token: LpfcsmRXFlqLYOhNby2P0IoVCiObSaKHUc7NAHyM

Requirements: Python 3.9+ and Node.js/npm compatible with the versions in [frontend/package.json](frontend/package.json). The demo works without AWS in rules-only mode. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install PyYAML
python -m webapi.server --port 8080 --ai off
```

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open the local URL printed by Vite. To build the frontend for the Python server instead, run `npm run build` in `frontend/`, then open `http://127.0.0.1:8080` while the API server is running. See the [frontend guide](frontend/README.md) for the teacher view and editor details.

For a terminal-only walkthrough from the repository root:

```bash
python -m engine.demo
```

## What the prototype does

1. A student chooses a grade and takes a readiness check, or skips directly to coding.
2. Rules use assessment evidence to determine eligible pathways; an optional Bedrock model can choose among them. Rules provide a fallback.
3. The student works through a project, runs checks, and receives feedback and practice. Progress is tracked by concept.
4. The student can view course progress; a token-protected teacher view displays prototype reporting.

Students can import results from an earlier lesson or choose a sample profile. Project suggestions use their interests; skill evidence determines where they start. The diagnostic also has an optional [AgentCore deployment](deploy/agentcore/README.md).

The app also supports alternative project choices, a text/blocks editor, an optional AI tutor, and Bedrock Guardrails when configured. The configured Bedrock model is **not a verified Strands Decider 2B deployment**. The skill stages and pathway rules are a prototype rather than the full point-vector and prerequisite graph described in the specification.

## AWS and data

AI features require `boto3`, AWS credentials, model access, and the appropriate region. See [Bedrock and safety notes](documentation/archive/prototype-reference.md#safety-amazon-bedrock-guardrail). The server's working copy of student data is `.codeai-data/` (readable only by the server's own user). When `config/aws_storage.json` exists, every change is also saved to a private S3 bucket encrypted with its own KMS key, which only the app role can read or write, and the server restores from it on start. The curriculum is then read from a pinned S3 object version. Email addresses and phone numbers are taken out of student code before it is saved. See the [AWS storage guide](documentation/AWS_STORAGE_SETUP.md) for setup and what is stored.

## Tests and evaluation

From the repository root with the Python dependencies installed:

```bash
python -m unittest discover -s tests -t .
python -m engine.cli check-content
```

Frontend checks: `cd frontend && npm test && npm run typecheck`. The [evaluation guide](evaluation/README.md) explains the harnesses and test data. Published results include synthetic cases and earlier prototype runs; see the individual reports for their scope and limitations.

## Repository at a glance

| Path | Purpose |
|---|---|
| [`frontend/`](frontend/) | React student and teacher interfaces |
| [`webapi/`](webapi/) | HTTP API and server |
| [`engine/`](engine/) | Lesson grading, routing, progress, AI, and safety |
| [`diagnostic/`](diagnostic/) | Readiness check and placement |
| [`projects/`](projects/) | Authored projects, lessons, checks, and practice |
| [`evaluation/`](evaluation/) | Evaluation harnesses, datasets, and reports |
| [`documentation/`](documentation/) | Specifications, references, and repository guide |
| [`tests/`](tests/) | Python tests |

More locations, including the curriculum workbook and rubric references, are listed in the [repository guide](documentation/REPOSITORY_GUIDE.md). Team coordination is tracked in [collab.md](collab.md).

# Customer Support application reviewer

A small hiring agent for a **Customer Support Specialist** role. It reads an application, scores it from a fixed rubric, and calls one tool: `advance_to_interview`, `reject`, or `request_more_info`.

A rejection is stored as **waiting for human approval**. The script never marks a candidate as rejected.

Application text is candidate information. Instructions inside an application cannot change the rubric, the score, or the tool.

## How to run

### 1. Open the project

```bash
cd path/to/this-repo
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add an API key

```bash
cp .env.example .env
```

Open `.env` and set **one** of these providers.

**Option A — Groq (free, no card):** create a key at [console.groq.com/keys](https://console.groq.com/keys)

```bash
GROQ_API_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-120b
```

**Option B — Claude:** create a key at [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)

```bash
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5
```

If both keys are set, Groq is used by default. To force one provider:

```bash
LLM_PROVIDER=groq
```

or

```bash
LLM_PROVIDER=anthropic
```

### 5. Run the agent

```bash
python main.py
```

If `python` is not found, use:

```bash
python3 main.py
```

This reviews the 3 sample applications (Maria, John, Alex), prints every step in the terminal, and writes the full log to:

`logs/review-log.json`

### 6. Optional: run tests

```bash
python -m unittest tests.test_review
```

## What the agent does

1. Sends the application to the model as untrusted data and forces a call to `extract_application_facts`.
2. The model is the main reader: each fact must include an exact `evidence` quote from the application.
3. Code accepts a fact only when that quote really appears in the text. Injection text cannot invent evidence, so it cannot raise the score. A small regex parser is only a backup when the model omits a field.
4. Scores the grounded facts in code. A complete strong application can reach 100.
5. Asks the model to call one decision tool, using that score. The model may write the one-line reason; code still owns the score and the allowed tool.
6. If the model calls a different tool, or sends a different score, the call is blocked and logged.
7. `reject` writes `status: waiting_for_human_approval` and `human_approved: false`.

## Rubric

| Signal | Points |
| --- | ---: |
| 3 or more years in support | 35 |
| 2 years in support | 25 |
| 1 year in support | 20 |
| Under 1 year in support | 10 |
| No support experience | 0 |
| A named helpdesk tool (Zendesk and similar) | 15 |
| 40 or more tickets a day | 15 |
| 20–39 tickets a day | 10 |
| Any stated ticket volume below 20 | 5 |
| Fluent English | 10 |
| Each extra language | +5, cap 15 |
| Full-time | 6 |
| Can start within weeks | 4 |
| Specific factual detail | up to 10 |

Next step:

- **70–100:** `advance_to_interview`
- **20–69:** `request_more_info`
- **0–19:** `reject`, saved for a person to approve

On the required samples:

- **Maria (1):** 100, interview. Telecom call-centre experience, Zendesk, 60 tickets a day, English and Spanish, full-time, starts in 2 weeks.
- **John (2):** 0, rejection proposal waiting for a person. The note says he is motivated and has no experience.
- **Alex (3):** 29, request more information. Two years of e-commerce support are real. The sentence that says to ignore the rubric and assign 100 is ignored.

## Log

Each review records the application, any injection phrases, the model's tool calls, facts accepted from evidence, backup fills, dropped fields, the score, and the tool result. For a blocked call the log contains `policy_block`. If the model sends a score other than the rubric score, the log contains `score_override_blocked`.

## What I would add next

- A human step that can approve or overturn a rejection proposal.
- A larger regression pack of messy real-world applications.
- A second reviewer model that only sees the grounded facts, for comparison.

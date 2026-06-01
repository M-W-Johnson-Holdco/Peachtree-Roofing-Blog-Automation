# Cursor Handoff Prompt

Copy/paste this into Cursor as project context.

## Project

Repo: `Peachtree-Roofing/blog-automation`

Purpose: automated weekly blog pipeline for Peachtree Roofing & Exteriors / Peachtree Restorations. The pipeline finds timely Metro Atlanta roofing-related news, evaluates source quality, writes a GEO-optimized blog draft, sends it to Slack for human approval, collects revision feedback, and eventually posts approved content.

Primary pipeline:

```text
search.py -> evaluate.py -> write.py -> approve.py -> post.py
```

Current useful commands:

```bash
conda run -n blog-automation python search.py
conda run -n blog-automation python evaluate.py
conda run -n blog-automation python evaluate.py --mock
conda run -n blog-automation python write.py
conda run -n blog-automation python write.py --mock
conda run -n blog-automation python approve.py post --latest
conda run -n blog-automation python approve.py listen
conda run -n blog-automation python pipeline.py --send-to-slack
conda run -n blog-automation python pipeline.py --mock --send-to-slack
```

## Environment

The project uses a conda env named:

```text
blog-automation
```

Important `.env` vars:

```env
TAVILY_API_KEY=...
TOGETHER_API_KEY=...
TOGETHER_EVALUATION_MODEL=Qwen/Qwen2.5-7B-Instruct-Turbo
TOGETHER_WRITING_MODEL=Qwen/Qwen2.5-7B-Instruct-Turbo
AUTHOR_NAME=Jonathan Gil
AUTHOR_CREDENTIALS=Licensed Roofing Contractor, Metro Atlanta

SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_APPROVAL_CHANNEL=C1234567890
```

Note: user wants to use `Qwen/Qwen2.5-72B-Instruct-Turbo` for writing if possible. Together rejected it as `model_not_available` because it now requires a dedicated endpoint. `write.py` was updated to default to 7B serverless and automatically retry with the serverless fallback if an overridden model fails with `model_not_available`.

If using Together 72B dedicated endpoint:

- Create/start a dedicated endpoint on Together.
- Use endpoint ID for start/stop automation.
- Use the deployed model name in `TOGETHER_WRITING_MODEL`.
- Stop endpoint after each run to avoid hourly billing.
- Approximate dedicated cost discussed: H100 listed around `$3.99/hour`, so 5 minutes is roughly `$0.33`; the real risk is leaving the endpoint running.

## Current Search Strategy

`search.py` searches Tavily around four GEO content territories:

```text
storm_damage
ga_insurance_navigation
roof_safety
county_guides
```

It uses staged searches:

```text
priority_7_day_news
priority_30_day_news
broad_14_day_news
official_30_day_general
```

Priority sources include FOX 5 Atlanta, WSB-TV, AJC, 11Alive, weather.gov, Georgia General Assembly, and Georgia Department of Community Affairs.

Search results are saved to:

```text
output/sources/search_results.json
```

## Search Scoring Work Added This Session

The user requested improved search targeting:

- territory alignment reward
- multi-territory bonus
- negative scoring for sports/politics/generic/off-topic sources
- semantic relevance beyond keyword matching
- duplicate topic penalty versus drafts from the past 30 days

Implemented in `search.py`:

- `TERRITORY_SIGNAL_TERMS`
- `SEMANTIC_RELEVANCE_RULES`
- `OFF_TOPIC_PENALTY_TERMS`
- `_territory_alignment`
- `_semantic_relevance`
- `_off_topic_penalty`
- `_recent_draft_topics`
- `_duplicate_topic_penalty`
- richer result metadata:
  - `territory_alignment_score`
  - `matched_territories`
  - `multi_territory_bonus`
  - `semantic_relevance_score`
  - `semantic_relevance_rules`
  - `off_topic_penalty`
  - `off_topic_matches`
  - `duplicate_topic_penalty`
  - `duplicate_topic_match`
  - `duplicate_topic_overlap`

The semantic relevance check is deterministic and cheap: it looks for meaningful co-occurrence patterns like:

```text
storm + property/home/roof damage
insurance + homeowner/roof/claim
fire/safety + roof/building/attic
county + roof/permit/inspection
```

Smoke test result from session:

- off-topic Falcons sports example scored negative
- Cobb County hail/roof/homeowner example scored strongly

## Evaluation Stage

`evaluate.py` reads:

```text
output/sources/search_results.json
```

It writes:

```text
output/sources/evaluated_sources.json
output/sources/kept_sources.json
```

Evaluation categories now include:

```text
local_relevance
roofing_relevance
recency
source_authority
actionability
territory_alignment
semantic_relevance
```

Evaluation also applies metadata adjustments:

- multi-territory bonus increases adjusted score
- off-topic penalty decreases score or hard-rejects
- semantic relevance below threshold can hard-reject
- duplicate topic penalty can hard-reject if too similar to recent drafts

`prompts/evaluate.txt` was updated so the LLM sees the search metadata and scores territory/semantic relevance explicitly.

## Writing Stage

`write.py` reads:

```text
output/sources/kept_sources.json
feedback/style_notes.txt
```

It writes:

```text
output/drafts/YYYY-MM-DD-HHMMSS-title-slug.md
output/drafts/YYYY-MM-DD-HHMMSS-title-slug-validation.json
```

Important behavior:

- `--source-strategy auto|best|combine`
- default `auto` usually selects the best source unless several kept sources support the same strategy cluster
- `--feedback-json` lets Slack approval feedback be injected into a rewrite
- validator checks H1, answer-first intro, question headings, table, citation count, locations, FAQ count, author byline, CTA, no generic openers

Current writing model default:

```text
Qwen/Qwen2.5-7B-Instruct-Turbo
```

Reason: Together rejected `Qwen/Qwen2.5-72B-Instruct-Turbo` unless using a dedicated endpoint.

## Slack Approval Work Added This Session

`approve.py` was replaced with a Slack approval workflow.

Commands:

```bash
conda run -n blog-automation python approve.py post --latest
conda run -n blog-automation python approve.py post output/drafts/example.md
conda run -n blog-automation python approve.py listen
conda run -n blog-automation python approve.py listen --no-auto-rewrite
```

Behavior:

- posts draft preview/full draft thread to Slack
- saves approval JSON under `output/approvals/`
- green check reaction marks approved
- red X reaction asks for feedback in Slack thread
- human thread reply is saved into approval JSON
- by default, listener reruns `write.py --feedback-json <approval.json>` and posts the revision back to Slack

Slack app scopes discussed:

```text
chat:write
reactions:read
channels:history
groups:history
im:history
mpim:history
connections:write  # app-level token for Socket Mode
```

Socket Mode is recommended so no public webhook URL is needed.

## Together 72B Dedicated Endpoint Discussion

User wants 72B quality if affordable.

Key conclusion:

- Serverless 72B call failed.
- To use 72B, create a Together dedicated endpoint.
- Dedicated endpoints bill by uptime, not just per token.
- Automate start/write/stop if possible.

Suggested wrapper pattern:

```bash
#!/usr/bin/env bash
set -e

ENDPOINT_ID="endpoint-your-id"

tg endpoints start "$ENDPOINT_ID" --wait

cleanup() {
  tg endpoints stop "$ENDPOINT_ID" --wait
}
trap cleanup EXIT

python write.py
```

Important distinction:

```text
endpoint ID = used to start/stop the endpoint
model name = used in TOGETHER_WRITING_MODEL for inference
```

Also recommended: set Together endpoint auto-shutdown to 10-30 minutes as a billing safety net.

## Git / Worktree Warning

There are uncommitted changes in the repo from this session and previous session work. Do not blindly revert. Files touched include:

```text
.env.template
CHANGELOG.md
README.md
approve.py
evaluate.py
pipeline.py
prompts/evaluate.txt
requirements.txt
search.py
write.py
clean_output.py
```

`output/` is gitignored, but local runs may have generated drafts/evaluation JSON.

## Tests/Checks Run

Commands run successfully during session:

```bash
conda run -n blog-automation python -m py_compile approve.py write.py pipeline.py
conda run -n blog-automation python -m py_compile search.py evaluate.py
conda run -n blog-automation python evaluate.py --mock
conda run -n blog-automation python write.py --mock
conda run -n blog-automation python approve.py --help
conda run -n blog-automation python approve.py post --help
conda run -n blog-automation python approve.py listen --help
```

Slack live posting was not tested because real Slack credentials/channel were not provided.

Live Tavily search was not rerun after latest search scoring changes, so the next useful test is:

```bash
conda run -n blog-automation python search.py
conda run -n blog-automation python evaluate.py
conda run -n blog-automation python write.py
```

## Suggested Next Steps

1. Inspect `.env` and decide whether to keep serverless 7B or configure a Together 72B dedicated endpoint.
2. Run live `search.py` to see real candidates with the new scoring metadata.
3. Run live `evaluate.py` and inspect `output/sources/kept_sources.json`.
4. Run live `write.py` and inspect validation report.
5. Create/install Slack app, invite bot to channel, add Slack tokens to `.env`.
6. Test `approve.py post --latest`.
7. Run `approve.py listen` and test green check / red X / thread feedback flow.


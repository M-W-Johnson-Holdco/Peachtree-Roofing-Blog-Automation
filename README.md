# Peachtree Restorations Blog Automation

This project is an automated blog-post pipeline for Peachtree Restorations. Its goal is to find timely Metro Atlanta roofing, storm, insurance, building-code, HOA, and exterior-repair news, turn the best sources into a GEO-optimized blog draft, send the draft for approval, and eventually publish approved posts to the company website.

The finished pipeline is intended to run every Monday morning through GitHub Actions. It will search for relevant local news, evaluate whether each source is useful, generate a draft in Peachtree's editorial style, email the draft for review, and publish only after approval.

Current build status: the project scaffold exists, the Tavily web search module is in progress, and the later evaluation, writing, approval, and posting modules are still placeholders.

## Project layout

```
blog-automation/
├── src/peachtree_blog/          # Application code
│   ├── paths.py                 # Repo root + output/prompt paths
│   ├── used_sources.py          # Shared source URL tracking
│   ├── draft_approval.py        # Approval metadata in validation JSON; approved/ moves
│   ├── cli_progress.py          # Terminal progress helpers
│   ├── draft_pdf.py             # Markdown → PDF
│   ├── write_common.py          # Prompts, validation, Together helpers
│   ├── together_endpoint.py     # Optional dedicated endpoint management
│   ├── pipeline/                # search, evaluate, write_serverless, approve_listen, cli, runner
│   └── tools/                   # clean_output, etc.
├── pipeline.py                  # Entry: interactive menu (``--all`` for full run)
├── prompts/                     # LLM prompt templates
├── feedback/                    # Standing style notes
├── output/                      # Generated JSON, drafts, approved (gitignored)
└── scripts/                     # Shell helpers
```

### Running stages

From the repo root, install once (recommended for `conda run` and `python -m`):

```bash
pip install -e .
```

Or set `export PYTHONPATH=src` for ad-hoc runs without installing.

**Interactive menu** (default — pick search, evaluate, write, or approve):

```bash
python pipeline.py
```

**Full pipeline** (search → evaluate → write, non-interactive — CI/scripts):

```bash
python pipeline.py --all
python pipeline.py --all --send-to-slack
```

**Single stage**:

```bash
python pipeline.py --stage search
python pipeline.py --stage evaluate
python pipeline.py --stage write
```

**Run a module directly** (after `pip install -e .` or `export PYTHONPATH=src`):

```bash
python -m peachtree_blog.pipeline.search
python -m peachtree_blog.pipeline.evaluate
python -m peachtree_blog.pipeline.write_serverless
python -m peachtree_blog.pipeline.approve_listen
python -m peachtree_blog.tools.clean_output
```

## Webscraping

The first stage of the pipeline lives in `search.py`. This module searches the web for recent Metro Atlanta topics that could support a useful roofing blog post.

### API Used

The project uses the Tavily Search API through the `tavily-python` package.

Tavily is used because it returns structured search results that are easier to pass into an AI evaluation step than a raw search-results page. Each result includes fields like:

- `title`
- `url`
- `content`
- `published_date`
- `score`

The API key is stored locally in `.env` as:

```env
TAVILY_API_KEY=your_key_here
```

`.env` is ignored by git and should never be committed.

### How Search Works

`search.py` is aligned with the Peachtree GEO content strategy in `resources/Peachtree_GEO_Content_Strategy_2026 (1).pdf`.

The search plan is organized around the four topical territories from the strategy:

- `storm_damage`: Metro Atlanta storm damage inspection and repair.
- `ga_insurance_navigation`: Georgia roof insurance claims, RCV vs. ACV, HB511, and deductible guidance.
- `roof_safety`: Atlanta roof safety, fires, penetrations, construction safety, and structural risk.
- `county_guides`: County-specific roof guidance for Fulton, DeKalb, Cobb, Gwinnett, Cherokee, and nearby service areas.

`search.py` currently:

1. Loads `TAVILY_API_KEY` from the project-level `.env` file.
2. Builds strategy-clustered search queries from the four GEO topical territories.
3. Runs staged searches: 7-day priority sources, 30-day priority sources, 14-day regional secondary outlets, 14-day broader news, then official sources if needed.
4. Uses Tavily's `news` topic for news stages and `general` topic for official-source fallback.
5. Uses `advanced` search depth.
6. Prioritizes trusted Atlanta and Georgia sources.
7. Deduplicates results by URL, keeping the strongest strategy match for duplicate URLs.
8. Normalizes each result into a consistent JSON shape.
9. Enforces the published-date window locally because search APIs can sometimes return stale pages.
10. Filters results for local Atlanta/Georgia relevance.
11. Filters results for the strategy's event-hook categories: storms, insurance, legislation, fire, safety, construction, permits, damage, and roof/exterior terms.
12. Applies cluster-specific gates so storm, insurance, roof-safety, and county-guide results each prove the right kind of relevance.
13. Blocks common false positives like sports, car insurance, liability-only legal stories, shootings, and election/runoff articles.
14. Adds strategy metadata to each result, including `strategy_cluster`, `pillar_topic`, `trigger_window_hours`, `search_stage`, `search_quality_score`, and `matched_terms`.
15. Skips source URLs already recorded in `output/sources/used_sources.json` from previously approved (published) blogs.
16. Saves the final result list to `output/sources/search_results.json`.

Run it with:

```bash
conda run -n blog-automation python -m peachtree_blog.pipeline.search
```

Useful flags:

```bash
# Default: 8 rotating queries (2/cluster), early stop at 10 results (~8–32 credits typical)
conda run -n blog-automation python -m peachtree_blog.pipeline.search

# Full 27-query plan (higher credit usage)
conda run -n blog-automation python -m peachtree_blog.pipeline.search --all-queries

# Keep searching until 25 candidates are found (default is 10)
conda run -n blog-automation python -m peachtree_blog.pipeline.search --target-results 25

# Run every stage and every query regardless of target (~80–270 credits)
conda run -n blog-automation python -m peachtree_blog.pipeline.search --all-stages --all-queries
```

### Priority Sources

The current search module prioritizes:

- FOX 5 Atlanta
- WSB-TV
- AJC
- 11Alive
- National Weather Service / weather.gov
- Georgia General Assembly
- Georgia Department of Community Affairs

These sources are preferred because they are more likely to produce credible local facts that can be cited in a blog post.

### Secondary Regional Sources

A dedicated secondary stage searches these Metro Atlanta outlets:

- CBS46 / Atlanta News First
- Atlanta Magazine (`atlantan.com`)
- Marietta Daily Journal
- Gwinnett Daily Post
- Rockdale Newton Citizen
- AccessWDUN
- Reporter Newspapers (Dunwoody/Brookhaven)
- Northside Neighbor

Secondary outlets receive a moderate authority bonus in `evaluate.py` (below priority TV/gov sources, above generic web hits).

### Search Cost

Tavily does not bill search by LLM tokens. It uses API credits.

The current module uses `search_depth="advanced"`. Tavily's current docs state that:

- `basic` search costs 1 API credit per request.
- `advanced` search costs 2 API credits per request.

By default, search uses **weekly query rotation**: 2 queries per strategy cluster (8 active queries) instead of all 27. Each advanced call costs 2 credits:

```text
8 active queries * 2 credits = 16 Tavily API credits per full stage
```

Credit savers built in:

- **Weekly query rotation** — `--queries-per-cluster 2` (default); use `--all-queries` for the full 27-query plan.
- **Between-stage early stop** — stops when `--target-results` (default: 10) is reached.
- **Within-stage early stop** — skips remaining queries in the current stage once the target is hit.

Worst case with defaults (all 5 stages, every rotated query):

```text
16 credits/stage * 5 stages = 80 Tavily API credits
```

Typical weekly run (target hit during stage 1–2, mid-stage exit):

```text
~8–32 Tavily API credits
```

Use `--all-queries` for maximum coverage (up to ~270 credits if all five stages run every query). Use `--all-stages` only when debugging.

Sources:

- Tavily Search API docs: https://docs.tavily.com/documentation/api-reference/endpoint/search
- Tavily credits and pricing docs: https://docs.tavily.com/documentation/api-credits

### Current Search Behavior

The current filter is intentionally strict. If Tavily finds Atlanta stories that are unrelated to roofing, storms, insurance, building safety, or exterior repair, those stories are filtered out before they reach the next pipeline stage.

At the moment, the search stage favors precision over raw volume, but it now targets up to 10 kept candidates before stopping (configurable with `--target-results`). A quiet local news week may still produce fewer results if filters reject off-topic stories. That is acceptable because the evaluation stage should receive fewer, cleaner candidates rather than many unrelated articles.

Search scoring now includes:

- Territory alignment scoring for the four GEO territories.
- A multi-territory bonus when one source bridges more than one useful content territory.
- Semantic relevance checks that require meaningful combinations, such as storm plus property damage or insurance plus roof/homeowner impact.
- Graduated recency scoring (1-day breaking news scores higher than week-old stories).
- Headline homeowner-relevance scoring for search-intent language in titles.
- Seasonal alignment bonus for storm and roof-safety clusters during Atlanta peak storm months.
- Content depth scoring based on Tavily snippet length.
- Actionability scoring for homeowner next-step language.
- Negative scoring for sports, politics, unrelated insurance, crime-only stories, and generic local news.
- Duplicate-topic penalties when a source overlaps a draft topic from the past 30 days.
- Permanent URL blocking via `output/sources/used_sources.json` so story URLs from approved blogs are skipped in future searches.

Candidates must reach `--min-quality-score` (default: 7.5) to be kept. Lower it with `--min-quality-score 6` if a quiet news week returns too few results.

### Used Source Registry

When a draft is **approved in Slack** (`approve_listen.py` ✅ reaction), its source URLs are appended to:

```text
output/sources/used_sources.json
```

Drafts that were only written but not approved do not block future searches. The next `search.py` run skips approved-source URLs automatically. `evaluate.py` also hard-rejects them as a backup if an old search file still contains them.

Useful commands:

```bash
# List recorded used sources
conda run -n blog-automation python used_sources.py --list

# Backfill from an already-approved draft's validation JSON
conda run -n blog-automation python used_sources.py --seed-validation output/drafts/drafts_json/<draft>-validation.json

# Seed the registry from a kept-sources file (manual override)
conda run -n blog-automation python used_sources.py --seed output/sources/kept_sources.json

# Allow previously used URLs again for one search run
conda run -n blog-automation python -m peachtree_blog.pipeline.search --include-used-sources
```

Mock writes do not update the registry.

The next planned improvement is a separate evergreen/reference-source lane for statistics and background citations, so the news-hook search can stay strict while the writing stage still receives enough authoritative supporting data.

## Source Evaluation

The second stage of the pipeline lives in `evaluate.py`. This module scores Tavily results before the writing stage uses them.

Evaluation exists because search results are only candidates. A local news site can still return sports, politics, syndicated stories, or page-navigation text that mentions weather without supporting a useful roofing article. `evaluate.py` is the quality gate that rejects those weak sources.

### API Used

The evaluation stage uses Together AI through the `together` Python package.

The default evaluation model is:

```text
Qwen/Qwen2.5-7B-Instruct-Turbo
```

You can override that model in `.env`:

```env
TOGETHER_API_KEY=your_key_here
TOGETHER_EVALUATION_MODEL=Qwen/Qwen2.5-7B-Instruct-Turbo
```

### How Evaluation Works

`evaluate.py` currently:

1. Reads candidates from `output/sources/search_results.json`.
2. Loads the evaluation prompt from `prompts/evaluate.txt`.
3. Sends each source to Together AI for scoring.
4. Scores five dimensions: local relevance, roofing relevance, recency, source authority, and actionability.
5. Preserves the strategy metadata from search, including `strategy_cluster`, `pillar_topic`, and `trigger_window_hours`.
6. Adds a `recommended_angle` for the future blog-writing stage.
7. Writes all scored sources to `output/sources/evaluated_sources.json`.
8. Writes sources with `weighted_score >= 5.0` to `output/sources/kept_sources.json`.

Run evaluation with:

```bash
conda run -n blog-automation python -m peachtree_blog.pipeline.evaluate
```

Requires `TOGETHER_API_KEY` in `.env`.

## Blog Writing

The third stage lives in `write_serverless.py`. It turns evaluated source candidates into a Markdown blog draft.

### API Used

The writing stage uses Together AI through the `together` Python package.

The default writing model is:

```text
Qwen/Qwen2.5-7B-Instruct-Turbo
```

You can override that model in `.env`:

```env
TOGETHER_WRITING_MODEL=Qwen/Qwen2.5-7B-Instruct-Turbo
```

Serverless mode retries with a fallback model if Together rejects the chosen model (unless `--dedicated-endpoint` is used).

### Serverless writing (default)

```bash
conda run -n blog-automation python -m peachtree_blog.pipeline.write_serverless
```

Interactive terminal runs show a model menu (default: Qwen3 235B tput). Serverless mode ignores `TOGETHER_DEDICATED_ENDPOINT_ID` unless you pass `--dedicated-endpoint`.

### Generation metadata in validation JSON

Each `*-validation.json` file includes a `generation` object:

- `runner` — `peachtree_blog.pipeline.write_serverless`
- `mode` — `serverless` or `dedicated`
- `model_used` — Together model billed for inference
- `elapsed_seconds` — API generation time
- `usage` — prompt/completion/total tokens from Together
- `estimated_cost_usd.tokens` — estimated token cost from Together catalog pricing

For dedicated runs, optional `TOGETHER_ENDPOINT_COST_PER_MINUTE` in `.env` adds endpoint uptime cost and `combined_total`.

### 72B Dedicated Endpoint (Auto Start/Stop)

`Qwen/Qwen2.5-72B-Instruct-Turbo` requires a Together dedicated endpoint. To avoid leaving it running (and billing) between runs, set these in `.env`:

```env
TOGETHER_DEDICATED_ENDPOINT_ID=endpoint-c2a48674-9ec7-45b3-ac30-0f25f2ad9462
TOGETHER_WRITING_MODEL=your-username/Qwen/Qwen2.5-72B-Instruct-Turbo-suffix
```

With `--dedicated-endpoint` and `TOGETHER_DEDICATED_ENDPOINT_ID` in `.env`, the writer:

1. Starts the endpoint and waits until it is ready.
2. Generates the draft.
3. Stops the endpoint on exit, even if generation fails.

Endpoint startup uses two timeouts:

- `TOGETHER_ENDPOINT_DEPLOY_TIMEOUT` (default 40 min): hardware provisioning while state is `PENDING`. Shows elapsed time only, no percent bar.
- `TOGETHER_ENDPOINT_START_TIMEOUT` (default 15 min): becoming ready while state is `STARTING`. The percent bar uses this budget only after deploy completes.

While running in a terminal, the writer shows live progress bars during endpoint start/stop and draft generation. Disable with `--no-progress` or `WRITE_NO_PROGRESS=1`.

`pipeline.py` and `approve_listen.py` call the writer module directly for Slack rewrites.

One-time setup with the Together CLI:

```bash
bash scripts/create_writing_endpoint.sh
```

Set the endpoint's inactive timeout to 10-30 minutes in Together as a billing safety net if your machine crashes mid-run.

Alternative CLI wrapper (if you prefer `tg` over the Python SDK):

```bash
bash scripts/write_with_endpoint.sh
```

### How Writing Works

`write_serverless.py`:

1. Reads kept sources from `output/sources/kept_sources.json`.
2. Loads the blog-writing prompt from `prompts/blog.txt`.
3. Loads editor feedback from `feedback/style_notes.txt`.
4. Formats source excerpts, evaluation reasons, strategy clusters, and recommended angles into a source block.
5. Calls Together AI to generate a Markdown draft.
6. Saves the draft to `output/drafts/drafts_md/YYYY-MM-DD-HHMMSS-title-slug.md`.
7. Saves a matching PDF to `output/drafts/drafts_pdf/YYYY-MM-DD-HHMMSS-title-slug.pdf`.
8. Saves a validation report to `output/drafts/drafts_json/YYYY-MM-DD-HHMMSS-title-slug-validation.json`.

By default, existing drafts are kept; new runs add timestamped files. Approval rewrites delete only the replaced draft's three files. Use `--clear-drafts` to wipe draft subdirectories before writing. With `--dedicated-endpoint`, use `--keep-drafts` to skip the pre-run clear. Use `--no-pdf` to skip PDF export.

Run live writing:

```bash
conda run -n blog-automation python -m peachtree_blog.pipeline.write_serverless
```

Dedicated endpoint:

```bash
conda run -n blog-automation python -m peachtree_blog.pipeline.write_serverless --dedicated-endpoint
```

Default `--source-strategy auto` creates one draft by either:

- combining sources when multiple strong sources support the same strategy cluster and blog angle
- choosing the strongest source when kept sources point to different topics

You can override this behavior:

```bash
conda run -n blog-automation python -m peachtree_blog.pipeline.write_serverless --source-strategy best
conda run -n blog-automation python -m peachtree_blog.pipeline.write_serverless --source-strategy combine
```

### Draft Validation

After generation, the writer checks the draft for core GEO requirements:

- H1 title exists.
- Opening paragraph is roughly 50-120 words.
- H2 headings are questions, except the exact `## FAQ` heading.
- A comparison table exists.
- Citation count is 3-5.
- At least 6 Metro Atlanta locations appear.
- FAQ has exactly 8 H3 question headings.
- Author byline exists.
- Final CTA exists.
- Generic openers are absent.

The validator is intentionally strict. A failed validation does not mean the file was not generated; it means the draft needs prompt tuning or revision before approval.

## Slack Approval

The approval stage lives in `approve_listen.py`. It posts the newest generated draft to Slack, stores approval state inside each draft's `*-validation.json` under `output/drafts/drafts_json/`, and listens for approval reactions and thread feedback. When a draft is approved, its `.md`, `.pdf`, and validation JSON move to `output/approved/` (same `drafts_md/`, `drafts_pdf/`, `drafts_json/` layout).

### Slack App Setup

Create a Slack app and install it into the company workspace. The bot needs these OAuth scopes:

```text
chat:write
files:write
reactions:read
reactions:write
channels:history
groups:history
im:history
mpim:history
```

When a PDF exists beside the draft (the default from `write_serverless.py`),
`approve_listen post` uploads that existing PDF to Slack. It does not generate or modify files
in `output/drafts/`.

Use only the history scopes that match where the approval message will be posted. A public channel needs `channels:history`; a private channel needs `groups:history`; a group DM needs `mpim:history`.

Under **Event Subscriptions**, enable events and subscribe to these **bot events**:

```text
reaction_added
reaction_removed
message.groups    # private approval channel
message.channels  # public approval channel
```

For local listening without a public webhook URL, enable Socket Mode and create an app-level token with:

```text
connections:write
```

Add the Slack settings to `.env`:

```env
SLACK_APPROVAL_BOT_TOKEN=xoxb-your-bot-token
SLACK_APPROVAL_TOKEN=xapp-your-app-token
SLACK_APPROVAL_CHANNEL=C1234567890
```

`SLACK_APPROVAL_CHANNEL` should be a Slack channel-like ID, not a display name. Invite the bot to the approval channel before posting.

### Post A Draft

Post the latest generated draft to Slack:

```bash
conda run -n blog-automation python -m peachtree_blog.pipeline.approve_listen post --latest
```

Or post a specific draft:

```bash
conda run -n blog-automation python -m peachtree_blog.pipeline.approve_listen post output/drafts/drafts_md/example.md
```

The message asks reviewers to react on the **intro message** (not the PDF thread reply):

- `:white_check_mark:` — approve (records sources in `used_sources.json`)
- `:x:` — request revisions (reply in thread with feedback)
- `:repeat:` (🔁) — discard the draft and rerun **search → evaluate → write**, then post a new draft for approval
- `:globe_with_meridians:` — after approval, publish to the company website (when PSAI env vars are set)

The bot pre-adds those reaction prompts on the intro message.

Posting updates the draft validation JSON with an `approval` block (Slack channel, message timestamp, status, feedback, etc.):

```text
output/drafts/drafts_json/YYYY-MM-DD-HHMMSS-title-slug-validation.json
```

After approval, the same files live under `output/approved/`.

To post and immediately start listening for reactions in one command:

```bash
conda run -n blog-automation python -m peachtree_blog.pipeline.approve_listen post --latest --then-listen
```

Or use the shortcut:

```bash
conda run -n blog-automation python -m peachtree_blog.pipeline.approve_listen
```

### Listen For Approval

Reactions are only processed while the listener is running. Start it in a separate terminal, or use `--then-listen` when posting.

Run the Socket Mode listener:

```bash
conda run -n blog-automation python -m peachtree_blog.pipeline.approve_listen listen
```

When a reviewer reacts with `:white_check_mark:` on the **intro message** (not the PDF thread reply), the validation JSON `approval.status` changes to `approved`, the draft moves to `output/approved/`, and the bot replies in the thread. If Predictive Sales AI is configured, the bot also offers a `:globe_with_meridians:` reaction to publish the post to the website (or publishes immediately when `PSAI_AUTO_PUBLISH=true`).

When a reviewer reacts with `:x:`, the bot asks for feedback in the Slack thread. The next human thread reply is saved into the validation JSON and `write_serverless.py` is rerun with:

```bash
python -m peachtree_blog.pipeline.write_serverless --feedback-json output/drafts/drafts_json/example-validation.json
```

The revised draft is then posted back to Slack for another approval round. To collect feedback without automatically rewriting, run:

```bash
conda run -n blog-automation python -m peachtree_blog.pipeline.approve_listen listen --no-auto-rewrite
```

### Clear Bot Messages From The Approval Channel

The bot can only delete **its own** messages (intro posts, PDF uploads, thread replies like “Approved by…”). Human messages and other apps are left untouched.

Preview what would be removed:

```bash
conda run -n blog-automation python -m peachtree_blog.pipeline.approve_listen clear-channel --dry-run
```

Delete after confirmation (or pass `--yes`):

```bash
conda run -n blog-automation python -m peachtree_blog.pipeline.approve_listen clear-channel
conda run -n blog-automation python -m peachtree_blog.pipeline.approve_listen clear-channel --yes
```

Uses `SLACK_APPROVAL_CHANNEL` from `.env`. Requires `channels:history` (or `groups:history` for private channels) and `chat:write`.

### Pipeline Posting

To run the normal pipeline and post the created draft to Slack:

```bash
conda run -n blog-automation python pipeline.py --all --send-to-slack
```

## Website Publishing (Predictive Sales AI)

After a draft is approved, you can publish it to the Peachtree website through Spectrum Predictive Sales AI (`POST /v1/blogs`).

**Secret (`.env` and GitHub Actions):** only `PSAI_API_KEY`.

**Non-secret settings** live in [`config/psai.json`](config/psai.json) (committed to the repo):

```json
{
  "api_url": "https://developers.predictivesalesai.com",
  "author": "j.gil@peachtreerestorations.com",
  "default_status": "draft",
  "auto_publish": false
}
```

Local `.env`:

```env
PSAI_API_KEY=your-bearer-key-with-blogs-write-scope
```

`author` must match a PSAI tenant user (email or username). `default_status` is `published`, `draft`, or `submitted`. Env vars still override `config/psai.json` when set.

### Slack flow

1. Approve with `:white_check_mark:` as usual.
2. If `PSAI_AUTO_PUBLISH=false` (default), the bot replies with instructions to react `:globe_with_meridians:` on the approval message.
3. On publish success, the thread shows the blog ID and public URL. The validation JSON stores `approval.psai` metadata.

Set `auto_publish` to `true` in `config/psai.json` to skip the extra reaction and publish immediately after approval.

### CLI

Publish an approved draft manually (Markdown path or `*-validation.json`):

```bash
conda run -n blog-automation python -m peachtree_blog.post output/approved/drafts_json/example-validation.json
```

Preview the JSON payload without calling the API:

```bash
conda run -n blog-automation python -m peachtree_blog.post output/approved/drafts_md/example.md --dry-run
```

Override status or opt into subscriber email:

```bash
conda run -n blog-automation python -m peachtree_blog.post output/approved/drafts_md/example.md --status published --notify-subscribers
```

The GitHub **Publish to Website** workflow (`publish.yml`) calls the same module for manual PSAI posts. See [docs/github-actions.md](docs/github-actions.md) for the full automation setup (weekly schedule, secrets, and what still runs locally).

## GitHub Actions automation

| Workflow | When | What |
|----------|------|------|
| **Weekly Blog Pipeline** | Monday 8 AM ET + manual | Search → evaluate → write → post draft to Slack |
| **Publish to Website** | Manual | PSAI `POST /v1/blogs` for an approved draft |

Slack **reactions** (✅ approve, 🌐 publish) still require `approve_listen listen` on your machine — GitHub Actions cannot run the Socket Mode listener.

Setup checklist: [docs/github-actions.md](docs/github-actions.md)

## Cleaning Test Output

Generated files under `output/` can be removed before a fresh test run.

Dry run:

```bash
conda run -n blog-automation python -m peachtree_blog.tools.clean_output
```

Actually delete generated output files:

```bash
conda run -n blog-automation python -m peachtree_blog.tools.clean_output --yes
```

The cleanup script only targets files under the project-level `output/` directory.

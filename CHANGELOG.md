# Peachtree Blog Pipeline Change Log

Use this file to record every meaningful project change: code edits, API decisions, workflow updates, prompt changes, test results, and blockers.

## Entry Template

```md
## YYYY-MM-DD - Short change title

Changed:
- 

Why:
- 

Files touched:
- 

Tested:
- 

Notes / next step:
- 
```

## 2026-06-03 - Reduce Tavily credits with query rotation and mid-stage early exit

Changed:
- Default search now runs 2 rotating queries per strategy cluster (8 active queries) based on ISO week number.
- Added within-stage early exit when `--target-results` is reached (skips remaining queries in that stage).
- Added CLI flags: `--queries-per-cluster`, `--all-queries`, `--rotation-week`.

Why:
- Cut typical weekly search usage from ~54–270 credits toward ~8–32 credits without losing staged priority/secondary/broad coverage.

Files touched:
- `search.py`
- `README.md`
- `CHANGELOG.md`

Tested:
- Verified `build_active_search_plan()` returns 8 queries with rotation and 27 with `--all-queries`.

## 2026-06-03 - Improve search scoring granularity in search.py

Changed:
- Added graduated recency, headline homeowner relevance, seasonal alignment, content depth, and actionability scores to `_quality_score`.
- Raised default minimum quality threshold from 6.0 to 7.5 (`--min-quality-score` to override).
- Persist new score fields on each search result JSON object.
- Added early-stop log message when `--target-results` is reached after a full stage.

Why:
- Prefer fresher, deeper, and more homeowner-actionable sources without changing existing territory, semantic, or off-topic filters.

Files touched:
- `search.py`
- `README.md`
- `CHANGELOG.md`

Tested:
- Ran Python syntax check for `search.py`.

## 2026-06-03 - Split draft outputs into drafts_md, drafts_pdf, and drafts_json

Changed:
- Draft Markdown, PDF, and validation JSON now save under `output/drafts/drafts_md/`, `drafts_pdf/`, and `drafts_json/`.
- Centralized draft path helpers in `write_common.py` (`output_paths`, `draft_pdf_path`, `latest_markdown_draft`, etc.).
- Updated `approve.py`, `search.py`, and rewrite cleanup to use the new layout with legacy flat-file fallback.

Why:
- Keep draft file types organized while preserving shared timestamped stems across formats.

Files touched:
- `write_common.py`
- `write_serverless.py`
- `approve.py`
- `approve_listen.py`
- `search.py`
- `README.md`
- `CHANGELOG.md`

Tested:
- Ran Python syntax check for modified modules.

## 2026-06-03 - Keep draft history in write_serverless; replace one draft on rewrite

Changed:
- `write_serverless.py` no longer clears all files in `output/drafts/` before each run.
- Slack approval rewrites remove only the replaced draft's Markdown, PDF, and validation JSON.
- Added `remove_draft_artifacts()` and `resolve_replace_draft_path()` in `write_common.py`.
- Replaced `--keep-drafts` with optional `--clear-drafts` on `write_serverless.py`.

Why:
- Preserve prior drafts while still replacing only the draft being revised.

Files touched:
- `write_common.py`
- `write_serverless.py`
- `README.md`
- `CHANGELOG.md`

Tested:
- Ran Python syntax check for `write_common.py` and `write_serverless.py`.

## 2026-06-02 - Track used source URLs and skip them in search

Changed:
- Added `used_sources.py` and `output/sources/used_sources.json` registry for story URLs used in blog drafts.
- `write.py` / `write_serverless.py` record selected source URLs after each non-mock draft save.
- `search.py` skips registry URLs by default; added `--include-used-sources` override.
- `evaluate.py` hard-rejects previously used URLs as a backup gate.
- Validation JSON now includes a `sources_used` block for traceability.

Why:
- Avoid reusing the same news story across multiple blog posts.

Files touched:
- `used_sources.py`
- `write_common.py`
- `search.py`
- `evaluate.py`
- `README.md`
- `CHANGELOG.md`

Tested:
- Ran Python syntax check for `used_sources.py`, `search.py`, `evaluate.py`, and `write_common.py`.

Notes / next step:
- Run `python used_sources.py --seed output/sources/kept_sources.json` once to block sources from drafts already written.

## 2026-06-02 - Expand search outlets, stages, and candidate volume

Changed:
- Raised default kept-result target from 5 to 15 and increased per-query result limits.
- Added `SECONDARY_SOURCES` with eight regional Metro Atlanta outlets and a new `secondary_14_day_news` Tavily stage.
- Added eight strategy queries (two per GEO cluster) for 27 total queries.
- Added `secondary_source` and `official_source` metadata on search results.
- Added CLI flags: `--target-results`, `--days-back`, `--max-results-per-query`, `--all-stages`.
- Log estimated and actual Tavily credit usage per run.
- Updated `evaluate.py` authority scoring for secondary (7) and official (8) sources.

Why:
- Find more candidates for evaluation while keeping search filters strict.
- Cover regional outlets beyond the original seven priority domains.

Files touched:
- `search.py`
- `evaluate.py`
- `README.md`
- `CHANGELOG.md`

Tested:
- Ran Python syntax check for `search.py` and `evaluate.py`.

Notes / next step:
- Run live `python search.py` and confirm more results in `output/sources/search_results.json`.
- Use `--all-stages` sparingly if staying inside Tavily's 1,000 free credits/month.

## 2026-06-02 - Make write_serverless.py fully standalone

Changed:
- Extracted shared draft-generation helpers into `write_common.py` (prompt building, validation, PDF/JSON output, generation metadata).
- Rewrote `write_serverless.py` as a standalone entry point that imports only from `write_common` — no `write.py` or `together_endpoint.py`.
- Slimmed `write.py` to dedicated-endpoint orchestration plus the same shared output path via `save_draft_outputs()`.

Why:
- `write_serverless.py` still called `write.main()`, which could start/stop a dedicated endpoint when `TOGETHER_DEDICATED_ENDPOINT_ID` was set in `.env`.

Files touched:
- `write_common.py`
- `write_serverless.py`
- `write.py`
- `CHANGELOG.md`

Tested:
- Ran `python write_serverless.py --mock`; confirmed `[write_serverless]` logs, no `[endpoint]` messages, and no import of `together_endpoint` or `write`.

Notes / next step:
- Use `write_serverless.py` for weekly serverless runs; keep `write.py` only when intentionally using a dedicated endpoint.

## 2026-06-01 - Fix raw endpoint fetch and auto-retry FAILED endpoints

Changed:
- Updated `fetch_endpoint_raw()` to pass `client.client` to `APIRequestor` (fixes `base_url` error).
- Auto-retry start when endpoint is in `FAILED` or `ERROR` state instead of exiting immediately.

Why:
- Rerun failed with `'Together' object has no attribute 'base_url'`.
- Together leaves endpoints in `FAILED` after a bad deploy; they can be restarted via API.

Files touched:
- `together_endpoint.py`
- `CHANGELOG.md`

Tested:
- Confirmed API restart moves endpoint from `FAILED` to `PENDING`.

## 2026-06-01 - Export PDF alongside Markdown drafts

Changed:
- Added `draft_pdf.py` to convert generated Markdown drafts to PDF via `markdown` + `xhtml2pdf`.
- `write.py` and `write_serverless.py` now save a matching `.pdf` next to each `.md` draft.
- Added `pdf_path` to validation JSON; added `--no-pdf` to skip export.
- Added `markdown` and `xhtml2pdf` to `requirements.txt`.

Why:
- Reviewers often want a shareable PDF in addition to the Markdown source file.

Files touched:
- `draft_pdf.py`
- `write.py`
- `write_serverless.py`
- `requirements.txt`
- `README.md`
- `CHANGELOG.md`

Tested:
- Ran PDF generation against an existing draft Markdown file.

## 2026-06-01 - Auto-clear output/drafts before writing

Changed:
- `write.py` and `write_serverless.py` now delete existing files in `output/drafts/` at the start of each run.
- Added `--keep-drafts` to skip cleanup when needed.

Why:
- Keep only the latest generated draft and validation report in the drafts folder.

Files touched:
- `write.py`
- `README.md`
- `CHANGELOG.md`

## 2026-06-01 - Tag generation metadata for write.py and write_serverless.py

Changed:
- Added `runner` and `mode` fields to validation JSON `generation` block for both entry points.
- `write_serverless.py` sets `WRITE_RUNNER=write_serverless.py` for clearer logs and JSON tagging.
- Summary logs now show model, token cost, and endpoint cost (when configured) using the correct runner prefix.
- Documented shared generation metadata in `README.md`.

Why:
- Serverless is the primary writing path; both scripts should record comparable timing and cost metadata.

Files touched:
- `write.py`
- `write_serverless.py`
- `README.md`
- `CHANGELOG.md`

## 2026-06-01 - Add generation timing and cost to draft validation JSON

Changed:
- Added token usage, generation elapsed time, model details, and estimated USD cost to draft validation JSON under `generation`.
- Added Together catalog pricing for common serverless writing models.
- Optional `TOGETHER_ENDPOINT_COST_PER_MINUTE` env var for dedicated endpoint uptime cost estimates.
- Print generation time and estimated token cost after each live run.

Why:
- Reviewers need visibility into model used, runtime, and inference cost per draft.

Files touched:
- `write.py`
- `.env.template`
- `CHANGELOG.md`

Tested:
- Ran Python syntax check for `write.py`.

## 2026-06-01 - Fix write_serverless still starting dedicated endpoint

Changed:
- Updated `write.py` to use `nullcontext(None)` when endpoint management is skipped.
- Fixed `managed_dedicated_endpoint(None)` incorrectly falling back to `TOGETHER_DEDICATED_ENDPOINT_ID` from `.env`.

Why:
- `write_serverless.py` set `TOGETHER_SKIP_ENDPOINT_MANAGEMENT=1` but the endpoint ID in `.env` was still picked up and started.

Files touched:
- `write.py`
- `CHANGELOG.md`

Tested:
- Ran Python syntax check for `write.py`.

## 2026-06-01 - Add write_serverless.py for Llama 3.3 70B serverless

Changed:
- Added `write_serverless.py` as a serverless writing entry point using `meta-llama/Llama-3.3-70B-Instruct-Turbo`.
- Skips dedicated endpoint start/stop even when `TOGETHER_DEDICATED_ENDPOINT_ID` remains in `.env`.

Why:
- Dedicated 72B deploys were unreliable; serverless 70B is a simpler path for draft generation.

Files touched:
- `write_serverless.py`
- `CHANGELOG.md`

Tested:
- Ran Python syntax check for `write_serverless.py`.

Notes / next step:
- Run `python write_serverless.py` for live serverless draft generation.

## 2026-06-01 - Prevent duplicate deploy messages on Together state flicker

Changed:
- Lock ready phase after first `STARTING` so brief `PENDING` flickers do not restart deploy.
- Print "Deploy complete" only once per start attempt.
- Clear the in-progress `\r` status line before phase transition prints.

Why:
- Together alternates `PENDING`/`STARTING` during deploy, which retriggered deploy phase and duplicated messages.

Files touched:
- `cli_progress.py`
- `together_endpoint.py`
- `CHANGELOG.md`

## 2026-06-01 - Fix endpoint progress labels and auto-retry FAILED deploys

Changed:
- Fixed progress display showing `deploying` label during the `STARTING` ready phase.
- Added `StatusTicker.reset_phase()` for clean phase transitions without stale labels.
- Auto-retry endpoint start up to 2 times when Together returns `FAILED`/`ERROR`.
- Surface Together `reason_for_state` in failure messages.
- Only print "Deploy complete" when a `PENDING` phase was actually observed.

Why:
- Live run showed wrong progress label and crashed after Together failed deploy with a generic start error.

Files touched:
- `cli_progress.py`
- `together_endpoint.py`
- `.env.template`
- `CHANGELOG.md`

Tested:
- Ran Python syntax check for `cli_progress.py` and `together_endpoint.py`.

## 2026-06-01 - Split endpoint deploy vs ready timeouts

Changed:
- Split endpoint startup into deploy (`PENDING`) and ready (`STARTING` → `STARTED`) phases.
- `TOGETHER_ENDPOINT_START_TIMEOUT` (default 900s) now applies only during the ready phase; deploy time no longer counts against it.
- Added `TOGETHER_ENDPOINT_DEPLOY_TIMEOUT` (default 2400s) for hardware provisioning.
- Deploy phase shows elapsed time only; percent bar starts once state reaches `STARTING`.
- Fetch endpoint status via raw API to handle Together `FAILED` state without SDK pydantic crashes.
- Skip stop attempts when endpoint is already in `FAILED` or `ERROR`.

Why:
- 72B endpoint deploy can exceed 10 minutes; the progress bar and timeout were misleading when deploy time consumed the start budget.
- Together returned `FAILED` state which crashed the SDK's strict pydantic model.

Files touched:
- `together_endpoint.py`
- `.env.template`
- `README.md`
- `CHANGELOG.md`

Tested:
- Ran Python syntax check for `together_endpoint.py`.

Notes / next step:
- If deploy fails with `FAILED`, check Together dashboard for hardware availability errors and retry.

## 2026-06-01 - Add live CLI progress for write.py

Changed:
- Added `cli_progress.py` with elapsed time, percent bars, and 5-second terminal updates.
- Updated `together_endpoint.py` to show progress while starting/stopping the dedicated endpoint.
- Updated `write.py` to show progress during Together draft generation (runs API call in a background thread).
- Added `--no-progress` flag and `WRITE_NO_PROGRESS=1` env override for CI/non-TTY runs.
- Documented `WRITE_PROGRESS_INTERVAL` and `WRITE_GENERATION_ESTIMATE_SECONDS` in `.env.template`.

Why:
- Endpoint startup and 72B generation can take several minutes; users wanted visible status in the terminal.

Files touched:
- `cli_progress.py`
- `together_endpoint.py`
- `write.py`
- `.env.template`
- `README.md`
- `CHANGELOG.md`

Tested:
- Ran Python syntax checks for `cli_progress.py`, `together_endpoint.py`, and `write.py`.
- Ran `python write.py --mock`.

Notes / next step:
- Run live `python write.py` in a terminal to see endpoint and generation progress bars.

## 2026-06-01 - Automate Together 72B dedicated endpoint start/stop

Changed:
- Added `together_endpoint.py` to start, wait for, and stop Together dedicated endpoints via the Python SDK.
- Updated `write.py` to wrap live generation in managed endpoint lifecycle when `TOGETHER_DEDICATED_ENDPOINT_ID` is set.
- Disabled serverless 7B fallback when a dedicated endpoint is configured so 72B failures are not silently downgraded.
- Added optional auto-detection of the deployed endpoint model name when `TOGETHER_WRITING_MODEL` is still the default 7B value.
- Added `scripts/create_writing_endpoint.sh` for one-time 72B endpoint creation with inactive auto-shutdown.
- Added `scripts/write_with_endpoint.sh` as a `tg` CLI wrapper alternative with `TOGETHER_SKIP_ENDPOINT_MANAGEMENT` to avoid double start/stop.
- Documented dedicated endpoint setup, env vars, and safety nets in `README.md` and `.env.template`.

Why:
- `Qwen/Qwen2.5-72B-Instruct-Turbo` requires a Together dedicated endpoint and bills by uptime, not just tokens.
- The writing stage should start the endpoint only when needed and stop it afterward, even if draft generation fails.

Files touched:
- `together_endpoint.py`
- `write.py`
- `scripts/create_writing_endpoint.sh`
- `scripts/write_with_endpoint.sh`
- `.env.template`
- `README.md`
- `CHANGELOG.md`

Tested:
- Ran Python syntax checks for `together_endpoint.py` and `write.py`.
- Ran `python write.py --mock`.

Notes / next step:
- Create the 72B dedicated endpoint in Together if not already deployed.
- Add `TOGETHER_DEDICATED_ENDPOINT_ID` and the deployed model name to `TOGETHER_WRITING_MODEL` in `.env`.
- Set Together endpoint inactive timeout to 10-30 minutes as a billing safety net.
- Run live `python write.py` and confirm endpoint start/stop behavior.

## 2026-06-01 - Add Slack approval workflow

Changed:
- Replaced the approval placeholder with `approve.py` commands for Slack draft posting and Socket Mode listening.
- Added approval JSON records under `output/approvals/`.
- Added green-check approval and red-X revision handling from Slack reactions.
- Added Slack thread feedback collection and automatic `write.py --feedback-json` rewrite support.
- Added `pipeline.py --send-to-slack` to post a draft after writing.
- Added Slack SDK dependency and Slack env vars to `.env.template`.
- Documented Slack app setup, posting, listening, and pipeline commands in `README.md`.

Why:
- Drafts need a practical human approval loop before publishing.
- Slack reactions and thread replies give reviewers a lightweight way to approve or request revisions.

Files touched:
- `approve.py`
- `write.py`
- `pipeline.py`
- `requirements.txt`
- `.env.template`
- `README.md`
- `CHANGELOG.md`

Tested:
- Ran Python syntax checks for `approve.py`, `write.py`, and `pipeline.py`.

Notes / next step:
- Install the new `slack_sdk` dependency.
- Create/install the Slack app, invite it to the approval channel, and add Slack tokens to `.env`.
- Run `approve.py post --latest` and `approve.py listen` with real Slack credentials.

## 2026-06-01 - Improve search targeting and scoring

Changed:
- Added territory alignment scoring to `search.py`.
- Added a multi-territory bonus for sources that bridge multiple GEO content territories.
- Added semantic relevance rules that score meaningful source intent beyond isolated keyword matches.
- Added negative scoring for sports, politics, unrelated insurance, crime-only stories, and generic local news.
- Added a duplicate-topic penalty against drafts from the past 30 days.
- Passed the new search metadata into `evaluate.py` and `prompts/evaluate.txt`.
- Expanded evaluation scoring with territory alignment and semantic relevance dimensions.

Why:
- Search candidates should be ranked by Peachtree content usefulness, not just by local/topic keyword overlap.
- Evaluation should penalize off-topic and recently repeated ideas before they reach the writing stage.

Files touched:
- `search.py`
- `evaluate.py`
- `prompts/evaluate.txt`
- `README.md`
- `CHANGELOG.md`

Tested:
- Ran Python syntax checks for `search.py` and `evaluate.py`.
- Ran `conda run -n blog-automation python evaluate.py --mock`.
- Ran a local smoke check comparing an off-topic sports source against a Cobb County storm/roof source.

Notes / next step:
- Run live `search.py` with Tavily to inspect the new scoring metadata on real candidates.

## 2026-06-01 - Add serverless writer model fallback

Changed:
- Changed the default writing model to `Qwen/Qwen2.5-7B-Instruct-Turbo`.
- Added an automatic retry when Together rejects an overridden non-serverless model with `model_not_available`.
- Updated `.env.template` and `README.md` to show the serverless writing model.

Why:
- Together rejected `Qwen/Qwen2.5-72B-Instruct-Turbo` because it now requires a dedicated endpoint.

Files touched:
- `write.py`
- `.env.template`
- `README.md`
- `CHANGELOG.md`

Tested:
- Ran Python syntax check for `write.py`.

## 2026-05-26 - Initial project scaffold and Tavily search module

Changed:
- Created the planned project structure for the blog automation pipeline.
- Added dependency list, environment template, gitignore, prompt files, feedback notes, workflow placeholders, and Python module stubs.
- Implemented `search.py` as the first runnable module.
- Added Tavily search queries for Metro Atlanta roofing, storm, insurance, HOA, code, fire, and housing-market topics.
- Added result normalization, URL deduplication, priority-source tagging, and JSON output to `output/drafts/search_results.json`.
- Added local and topic relevance filters to reduce unrelated Tavily results.

Why:
- Establish a clean foundation before building source evaluation, blog writing, approval email, and posting steps.
- Make the search step testable by itself before connecting it to the rest of the pipeline.
- Keep unrelated Atlanta stories from reaching `evaluate.py`.

Files touched:
- `search.py`
- `requirements.txt`
- `.env.template`
- `.gitignore`
- `prompts/evaluate.txt`
- `prompts/blog.txt`
- `feedback/style_notes.txt`
- `pipeline.py`
- `evaluate.py`
- `write.py`
- `approve.py`
- `post.py`
- `.github/workflows/weekly.yml`
- `.github/workflows/approve.yml`
- `output/drafts/search_results.json`

Tested:
- Confirmed the `blog-automation` conda environment uses Python 3.13.13.
- Installed required dependencies in the conda environment.
- Ran Python syntax checks for all current modules.
- Ran `search.py` with the Tavily API key from `.env`.
- Verified Tavily API connectivity works when network access is allowed.
- Verified strict search currently returns no relevant priority-source results from the past 7 days and writes an empty JSON array.

Notes / next step:
- Add fallback search behavior for quiet news weeks: 14-day priority-source search, then broader 7-day source search, then evergreen topic fallback.
- Build `evaluate.py` after search fallback behavior is in place.

## 2026-05-26 - Move webscraping code into its own folder

Changed:
- Created a `webscraping/` folder.
- Moved `search.py` to `webscraping/search.py`.
- Updated the moved module so it loads `.env` from the project root.
- Updated the default search output path so results still save to project-level `output/drafts/search_results.json`.
- Updated `evaluate.py` placeholder text to reference the new search module path.

Why:
- Keep web search and scraping-related code separate from later pipeline stages like evaluation, writing, approval, and posting.
- Make the project easier to navigate as more source-gathering logic gets added.

Files touched:
- `webscraping/search.py`
- `evaluate.py`
- `CHANGELOG.md`

Tested:
- Ran Python syntax check for `webscraping/search.py`.

Notes / next step:
- Run `conda run -n blog-automation python webscraping/search.py` after future search edits.
- Add `webscraping/__init__.py` if we start importing search functions as a package from `pipeline.py`.

## 2026-05-26 - Add project README documentation

Changed:
- Added `README.md`.
- Documented the project purpose as an automated blog-post pipeline for Peachtree Restorations.
- Added the first technical section for webscraping.
- Explained the Tavily API, current search flow, priority sources, output file, and search credit usage.
- Clarified that Tavily uses API credits rather than LLM tokens.

Why:
- Create a central project document that explains how the pipeline works as it is built.
- Make the webscraping stage understandable before adding evaluation and writing stages.

Files touched:
- `README.md`
- `CHANGELOG.md`

Tested:
- Verified Tavily credit details against current Tavily documentation before writing the README.

Notes / next step:
- Add sections for source evaluation, blog generation, approval email, posting, GitHub Actions, and environment setup as those stages are implemented.

## 2026-05-26 - Align search with Peachtree GEO content strategy

Changed:
- Updated `webscraping/search.py` to organize Tavily queries around the four strategy territories from `resources/Peachtree_GEO_Content_Strategy_2026 (1).pdf`.
- Added strategy clusters for storm damage, Georgia insurance navigation, roof safety, and county guides.
- Added metadata to each search result: `strategy_cluster`, `pillar_topic`, and `trigger_window_hours`.
- Expanded Metro Atlanta geographic terms using the strategy's county, city, and neighborhood examples.
- Expanded topic filtering to include strategy-relevant event hooks like safety, construction, permits, HVAC penetrations, RCV/ACV, HB511, deductibles, flashing, attic ventilation, and structural risk.
- Updated `README.md` to document the strategy-aligned search behavior and revised Tavily credit estimate.

Why:
- The search stage should produce sources that support Peachtree's GEO content territories, not just generic roofing news.
- Every source candidate should connect to either a fresh local event hook or a longer-term authority cluster.

Files touched:
- `webscraping/search.py`
- `README.md`
- `CHANGELOG.md`

Tested:
- Ran Python syntax check for `webscraping/search.py`.
- Live Tavily test was not run after this edit because network approval was rejected.

Notes / next step:
- Run `conda run -n blog-automation python webscraping/search.py` with network access to inspect strategy-aligned search results.
- If the result set is still too narrow, add the planned fallback search stages before implementing `evaluate.py`.

## 2026-05-26 - Implement source evaluation stage

Changed:
- Replaced the `evaluate.py` placeholder with a working source evaluator.
- Added live Together AI evaluation using `TOGETHER_API_KEY`.
- Added `--mock` mode for no-credit local testing.
- Added JSON parsing, score normalization, recency scoring, and output writing.
- Added `output/drafts/evaluated_sources.json` for all scored sources.
- Added `output/drafts/kept_sources.json` for sources that pass the keep threshold.
- Updated `prompts/evaluate.txt` with strategy-cluster metadata and `recommended_angle`.
- Added `TOGETHER_EVALUATION_MODEL` to `.env.template`.
- Updated `README.md` with source evaluation documentation.

Why:
- The writing stage needs a strict quality gate so unrelated Tavily results do not become blog sources.
- Evaluation should preserve Peachtree's GEO strategy metadata from search and turn source candidates into actionable blog angles.

Files touched:
- `evaluate.py`
- `prompts/evaluate.txt`
- `.env.template`
- `README.md`
- `CHANGELOG.md`
- `output/drafts/evaluated_sources.json`
- `output/drafts/kept_sources.json`

Tested:
- Ran Python syntax check for `evaluate.py`.
- Ran `conda run -n blog-automation python evaluate.py --mock`.
- Verified mock evaluation writes both output JSON files.
- Verified mock evaluation rejects the sports false positive and keeps one potentially usable local safety source.
- Confirmed `TOGETHER_API_KEY` is not set yet, without printing secret values.

Notes / next step:
- Add `TOGETHER_API_KEY` to `.env`.
- Run live evaluation with `conda run -n blog-automation python evaluate.py`.
- Review `kept_sources.json` before building `write.py`.

## 2026-05-26 - Switch evaluation default to available Together Qwen model

Changed:
- Changed the default evaluation model from `Qwen/Qwen2.5-32B-Instruct-Turbo` to `Qwen/Qwen2.5-7B-Instruct-Turbo`.
- Updated `.env.template` and `README.md` to match the new default.

Why:
- Together returned `model_not_available` for `Qwen/Qwen2.5-32B-Instruct-Turbo`.
- The 7B Qwen2.5 Turbo model is available on Together serverless and is sufficient for source classification and JSON scoring.

Files touched:
- `evaluate.py`
- `.env.template`
- `README.md`
- `CHANGELOG.md`

Tested:
- Ran live evaluation successfully with `Qwen/Qwen2.5-7B-Instruct-Turbo`.
- Verified Together rejected the unavailable `Qwen/Qwen2.5-32B-Instruct-Turbo` model before the switch.
- Verified live evaluation scored 2 sources, kept 1, and rejected the sports false positive.

Notes / next step:
- If higher evaluation quality is needed later, test another available Together model such as `Qwen/QwQ-32B`.

## 2026-05-26 - Improve search precision and fallback stages

Changed:
- Added staged Tavily search behavior to `webscraping/search.py`.
- Search now tries 7-day priority sources, 30-day priority sources, 14-day broader news, and official-source fallback.
- Added local date-window enforcement to reject stale Tavily results.
- Added URL deduplication that keeps the strongest strategy match for duplicate URLs.
- Added `search_stage`, `search_days`, `search_quality_score`, and `matched_terms` to saved search results.
- Added cluster-specific gates for storm damage, Georgia insurance navigation, roof safety, and county guides.
- Added false-positive filters for sports, car insurance, liability-only stories, shootings, and election/runoff articles.
- Lowered the default target result count to 5 to favor quality over volume.
- Updated `README.md` with the new staged search behavior and Tavily credit estimate.

Why:
- Earlier searches either returned too few sources or broadened into stale/irrelevant articles.
- The search stage should give `evaluate.py` a cleaner candidate set while still widening intelligently during quiet news weeks.

Files touched:
- `webscraping/search.py`
- `README.md`
- `CHANGELOG.md`
- `output/drafts/search_results.json`
- `output/drafts/evaluated_sources.json`
- `output/drafts/kept_sources.json`

Tested:
- Ran Python syntax check for `webscraping/search.py`.
- Ran live Tavily search.
- Verified stale 2023/2025/unknown-date archive results are rejected.
- Verified search output now contains 2 cleaner candidates.
- Ran live Together evaluation on the new search output.
- Verified evaluation kept 2/2 current search candidates.

Notes / next step:
- Add an evergreen/reference-source lane for statistics and supporting citations before implementing `write.py`.

## 2026-05-26 - Move search module back to project root

Changed:
- Moved `webscraping/search.py` to `search.py`.
- Removed the now-empty `webscraping/` directory and its generated Python cache.
- Updated `search.py` so `PROJECT_ROOT` resolves correctly from the root directory.
- Updated `README.md` commands and references to use `search.py`.

Why:
- Keep the first pipeline stage visible at the project root with the other main pipeline modules.

Files touched:
- `search.py`
- `README.md`
- `CHANGELOG.md`

Tested:
- Ran Python syntax check for `search.py` after the move.

Notes / next step:
- Run search from the root with `conda run -n blog-automation python search.py`.

## 2026-05-26 - Implement blog writing stage

Changed:
- Replaced the `write.py` placeholder with a working blog draft generator.
- Added source formatting from `output/drafts/kept_sources.json`.
- Added prompt loading from `prompts/blog.txt`.
- Added editor feedback injection from `feedback/style_notes.txt`.
- Added Together AI live generation using `TOGETHER_WRITING_MODEL`.
- Added `--mock` mode for local no-credit draft testing.
- Added Markdown draft output to `output/drafts/YYYY-MM-DD-title-slug.md`.
- Added validation report output to `output/drafts/YYYY-MM-DD-title-slug-validation.json`.
- Added validation checks for H1, answer-first opening, question H2s, comparison table, citations, location count, FAQ count, byline, CTA, and generic openers.
- Added `TOGETHER_WRITING_MODEL` to `.env.template`.
- Tightened `prompts/blog.txt` around FAQ formatting, H2 question headings, and byline formatting.
- Updated `README.md` with blog writing documentation.

Why:
- The pipeline needs a standalone writing stage that can turn evaluated sources into a reviewable Markdown draft.
- Validation gives fast feedback on whether the generated draft meets Peachtree's GEO standards before approval email work begins.

Files touched:
- `write.py`
- `prompts/blog.txt`
- `.env.template`
- `README.md`
- `CHANGELOG.md`
- `output/drafts/*.md`
- `output/drafts/*-validation.json`

Tested:
- Ran Python syntax check for `write.py`.
- Ran `conda run -n blog-automation python write.py --mock`.
- Ran live Together generation with `Qwen/Qwen2.5-7B-Instruct-Turbo`.
- Verified draft and validation report files are created.
- Confirmed the live draft currently fails some strict validation checks, which should be addressed in the next prompt/revision tuning pass.

Notes / next step:
- Tune `write.py` or `prompts/blog.txt` so live drafts reliably pass H2 question format, citation count, location count, and exact CTA checks.
- Consider testing a stronger available Together writing model before building `approve.py`.

## 2026-05-26 - Set writing default to Qwen2.5 72B

Changed:
- Changed the default writing model from `Qwen/Qwen2.5-7B-Instruct-Turbo` to `Qwen/Qwen2.5-72B-Instruct-Turbo`.
- Updated `.env.template` and `README.md` to match the new writing default.

Why:
- Blog drafting benefits more from the stronger 72B instruction model than source evaluation does.
- Evaluation can remain on the cheaper 7B model while writing uses the larger model.

Files touched:
- `write.py`
- `.env.template`
- `README.md`
- `CHANGELOG.md`

Tested:
- Ran Python syntax check for `write.py` after the model-default update.

Notes / next step:
- Run `conda run -n blog-automation python write.py` to verify your Together account can access the 72B serverless model.

## 2026-05-26 - Add one-draft source selection to writing stage

Changed:
- Added source-selection logic to `write.py`.
- Added `--source-strategy auto|best|combine`.
- Default `auto` mode now creates one draft by combining sources only when they support the same strategy cluster.
- If kept sources point to different blog angles, `auto` selects the strongest source by weighted score, roofing relevance, actionability, source authority, and local relevance.
- Added source-selection metadata to draft validation reports.
- Added timestamped draft filenames to prevent same-slug runs from overwriting each other.
- Updated `README.md` with the new source strategy behavior.

Why:
- Multiple unrelated sources were causing drafts to blend separate topics into one less coherent article.
- The writing stage should always produce one focused draft, either from a smart combination of aligned sources or from the best single source.

Files touched:
- `write.py`
- `README.md`
- `CHANGELOG.md`
- `output/drafts/*.md`
- `output/drafts/*-validation.json`

Tested:
- Ran Python syntax check for `write.py`.
- Ran `conda run -n blog-automation python write.py --mock`.
- Ran `conda run -n blog-automation python write.py --mock --source-strategy combine`.
- Verified default `auto` selected 1 of 2 current kept sources because they belong to different strategy clusters.
- Verified forced combine mode selected 2 of 2 current kept sources.
- Verified a timestamped mock validation report parses as valid JSON.

Notes / next step:
- Run live `write.py` with the 72B model and inspect whether focused single-source drafts pass more GEO validation checks.

## 2026-05-26 - Move source JSON outputs to output/sources

Changed:
- Updated `search.py` to save `search_results.json` to `output/sources`.
- Updated `evaluate.py` to read `output/sources/search_results.json`.
- Updated `evaluate.py` to save `evaluated_sources.json` and `kept_sources.json` to `output/sources`.
- Updated `write.py` to read `output/sources/kept_sources.json`.
- Updated `README.md` to document the new source-output location.

Why:
- Keep intermediate source/evaluation JSON separate from generated Markdown drafts and draft validation reports.

Files touched:
- `search.py`
- `evaluate.py`
- `write.py`
- `README.md`
- `CHANGELOG.md`
- `output/sources/search_results.json`
- `output/sources/evaluated_sources.json`
- `output/sources/kept_sources.json`

Tested:
- Ran Python syntax checks for `search.py`, `evaluate.py`, and `write.py`.
- Moved existing `search_results.json`, `evaluated_sources.json`, and `kept_sources.json` into `output/sources`.
- Ran `conda run -n blog-automation python evaluate.py --mock` and verified it reads/writes `output/sources`.
- Ran `conda run -n blog-automation python write.py --mock` and verified it reads `output/sources/kept_sources.json`.
- Verified `output/drafts` now contains generated Markdown drafts and validation reports, while source JSON files live in `output/sources`.

Notes / next step:
- Keep `output/drafts` for generated blog Markdown and validation reports only.

## 2026-05-26 - Add output cleanup script

Changed:
- Added `clean_output.py`.
- The script lists generated files under `output/` by default.
- Added `--yes` flag to actually delete generated output files.
- Updated `README.md` with cleanup commands.

Why:
- Make it easy to start each local pipeline test from a clean output directory.
- Keep deletion scoped to generated output files only.

Files touched:
- `clean_output.py`
- `README.md`
- `CHANGELOG.md`

Tested:
- Ran Python syntax check for `clean_output.py`.
- Ran `conda run -n blog-automation python clean_output.py` in dry-run mode.
- Verified dry-run lists generated files without deleting them.

Notes / next step:
- Use `conda run -n blog-automation python clean_output.py --yes` before full clean-slate test runs.

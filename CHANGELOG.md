# Peachtree Blog Pipeline Change Log

Use this file to record every meaningful project change: code edits, API decisions, workflow updates, prompt changes, test results, and blockers.

**Project rule:** After any meaningful code or workflow change, add a new dated entry at the top of the log (below this section). Agents and contributors should update `CHANGELOG.md` in the same PR or edit session as the change.

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

## 2026-06-11 - Relax search content filters for Georgia-wide and trade stories

Changed:
- Added `southeast` to `LOCAL_TERMS` and `STATE_LOCAL_TERMS`.
- Relaxed `georgia_only_without_metro_signal`: Georgia/Southeast + roofing, insurance, or trade terms in headline/lead now pass (not headline-only).
- Expanded `PRIMARY_CORE_ROOFING_TERMS` with `contractor`, `restoration`, `roof restoration`, and `milestone`.

Why:
- Broad search was rejecting valid Georgia-wide storm/insurance and trade/PR stories that lacked a metro city in the headline.

Files touched:
- `src/peachtree_blog/pipeline/search.py`
- `CHANGELOG.md`

Tested:
- Not run (no Tavily key in this session).

Notes / next step:
- Push and re-run weekly workflow.

## 2026-06-11 - Proceed with one kept source; keep searching for two

Changed:
- Incremental search requires **1** evaluated keep to proceed (`MIN_EVALUATED_KEPT_TO_PROCEED`); stops early at **2** (`TARGET_EVALUATED_KEPT`) or when the Tavily credit cap is hit.
- Added `--target-evaluated-kept` CLI flag; `--min-evaluated-kept` now means minimum to pass search (default 1).
- Cleared `output/sources/used_sources.json` (no published blogs yet).

Why:
- Weekly CI failed with one strong keep (8.57) because the old minimum was 2; pipeline should draft on one source but still try for a second until credits run out.

Files touched:
- `src/peachtree_blog/pipeline/evaluate.py`
- `src/peachtree_blog/pipeline/search.py`
- `output/sources/used_sources.json`
- `CHANGELOG.md`

Tested:
- Not run (no Tavily key in this session).

Notes / next step:
- Push and re-run weekly workflow.

## 2026-06-11 - Default search to broad + official (content-first)

Changed:
- Search default skips PRIORITY/SECONDARY/trade domain-locked Tavily stages; runs `broad_21_day_news` and `official_30_day_general` only.
- Added `resolve_search_stages()` and `--domain-stages` to restore the full 8-stage local-TV-first plan.
- Wired `--domain-stages` through `pipeline.py --all` and `run_pipeline_restart()`.

Why:
- Domain-locked stages burned most of the 100-credit budget and missed trade/PR/industry URLs; content filters still enforce Metro Atlanta + roofing relevance.

Files touched:
- `src/peachtree_blog/pipeline/search.py`
- `src/peachtree_blog/pipeline/runner.py`
- `src/peachtree_blog/pipeline/cli.py`
- `README.md`
- `CHANGELOG.md`

Tested:
- Not run (no Tavily key in this session).

Notes / next step:
- Re-run weekly workflow or `python pipeline.py --all --default`; use `--domain-stages` if you want FOX 5 / AJC-first discovery again.

## 2026-06-11 - Fix empty used_sources.json crash in CI

Changed:
- Restored valid `output/sources/used_sources.json` (accidentally emptied in prior commit).
- `load_used_sources()` treats missing/blank file as empty list instead of JSONDecodeError.

Why:
- Weekly pipeline crashed at search when checkout contained an empty used_sources.json.

Files touched:
- `output/sources/used_sources.json`
- `src/peachtree_blog/used_sources.py`
- `CHANGELOG.md`

Tested:
- Not run.

Notes / next step:
- Push and re-run Weekly Blog Pipeline.

## 2026-06-11 - Shorten STRATEGY_CLUSTERS Tavily queries

Changed:
- Rewrote all 58 queries in `STRATEGY_CLUSTERS` to shorter geo + topic phrases (removed repeated "Metro Atlanta"/"homeowners" stacks).

Why:
- Broader Tavily recall while downstream filters and evaluate still gate relevance.

Files touched:
- `src/peachtree_blog/pipeline/search.py`
- `CHANGELOG.md`

Tested:
- Not run.

Notes / next step:
- Run search locally or Weekly workflow with widen search; compare `evaluated_sources.json` scores.

## 2026-06-11 - Lower evaluate keep threshold to 5.0

Changed:
- `KEEP_THRESHOLD` in `evaluate.py` from 6.0 to 5.0 (incremental search stop condition and kept_sources filter).
- Updated `prompts/evaluate.txt` and README to match.

Why:
- Quiet news weeks were failing CI with 0 kept sources (e.g. scores 3.2 and 4.68 on the only two candidates).

Files touched:
- `src/peachtree_blog/pipeline/evaluate.py`
- `prompts/evaluate.txt`
- `README.md`
- `CHANGELOG.md`

Tested:
- Not run.

Notes / next step:
- Re-run Weekly Blog Pipeline; Newton County tornado (4.68) would still fail — need sources scoring >= 5.0.

## 2026-06-11 - Widen search option for manual Weekly workflow runs

Changed:
- `pipeline.py --all` accepts `--all-queries` and `--include-used-sources` (passed through `run_pipeline_restart`).
- `weekly.yml` workflow_dispatch inputs `widen_search` (default true) and `include_used_sources`; scheduled Monday runs unchanged.

Why:
- Manual CI runs failed when incremental search found 0 sources scoring >= 6.0 on a quiet news week.

Files touched:
- `src/peachtree_blog/pipeline/runner.py`
- `src/peachtree_blog/pipeline/cli.py`
- `.github/workflows/weekly.yml`
- `CHANGELOG.md`

Tested:
- Not run.

Notes / next step:
- Push and Run workflow with widen search enabled (default on manual runs).

## 2026-06-11 - Fix Actions pip install (pycairo / libcairo2)

Changed:
- Added `scripts/ci-apt-packages.sh` to install `libcairo2-dev` and `pkg-config` before `pip install` in CI.
- Applied to `weekly.yml`, `slack_approve.yml`, `publish.yml`, and `approve.yml`.
- Render webhook Dockerfile installs the same native libs for `xhtml2pdf`.

Why:
- Weekly Blog Pipeline failed at Install dependencies: `pycairo` could not find system `cairo` on ubuntu-latest.

Files touched:
- `scripts/ci-apt-packages.sh`
- `.github/workflows/weekly.yml`
- `.github/workflows/slack_approve.yml`
- `.github/workflows/publish.yml`
- `.github/workflows/approve.yml`
- `webhook/Dockerfile`
- `CHANGELOG.md`

Tested:
- Root cause confirmed from Actions run 27150200902 logs.

Notes / next step:
- Push and re-run Weekly Blog Pipeline.

## 2026-06-11 - Set Cloudflare wrangler repo to M-W-Johnson-Holdco

Changed:
- `workers/slack-events/wrangler.toml`: `GITHUB_REPOSITORY` set to `M-W-Johnson-Holdco/Peachtree-Roofing-Blog-Automation`.

Why:
- Ready for Worker deploy without manual placeholder edit.

Files touched:
- `workers/slack-events/wrangler.toml`
- `CHANGELOG.md`

Tested:
- Not run.

Notes / next step:
- Deploy Worker per `docs/cloudflare-workers-setup.md`.

## 2026-06-11 - Add Cloudflare Worker + Actions Slack approval path

Changed:
- Cloudflare Worker (`workers/slack-events/`) verifies Slack Events and dispatches `slack_approve.yml`.
- `.github/workflows/slack_approve.yml` runs `scripts/process_slack_event.py` with existing `approve_listen` handlers.
- Shared routing in `src/peachtree_blog/slack_actions/processor.py`; Render webhook refactored to use the same module.
- Setup guide: `docs/cloudflare-workers-setup.md`.

Why:
- Always-on Slack approval without Mac listener or paid Render; heavy approve/rewrite stays in GitHub Actions Python.

Files touched:
- `workers/slack-events/`
- `.github/workflows/slack_approve.yml`
- `src/peachtree_blog/slack_actions/`
- `scripts/process_slack_event.py`
- `src/peachtree_blog/slack_webhook/events.py`
- `src/peachtree_blog/slack_webhook/app.py`
- `docs/cloudflare-workers-setup.md`
- `docs/github-actions.md`
- `.env.template`
- `.gitignore`
- `CHANGELOG.md`

Tested:
- Python import smoke test; Worker deploy requires Cloudflare account.

Notes / next step:
- Follow `docs/cloudflare-workers-setup.md`: Cloudflare account, `wrangler deploy`, Slack Request URL.

## 2026-06-11 - Add cloud Slack webhook for approval without Mac listener

Changed:
- FastAPI Slack Events handler (`src/peachtree_blog/slack_webhook/`) with signature verification and background processing.
- CI archives drafts to `generated/runs/<run_id>/` via `scripts/archive_ci_draft.py`; `weekly.yml` commits `generated/` after Slack post.
- `generated_store.py` + `slack_index.json` map Slack message timestamps to validation JSON paths.
- Webhook syncs approval state back via `github_sync.py` (`generated/` + `output/sources/used_sources.json`).
- Docker/deploy files under `webhook/`; `requirements-webhook.txt`; docs in `docs/slack-webhook-setup.md`.
- Approval moves CI drafts to `generated/approved/`; fixed validation JSON move on relocate.

Why:
- GitHub Actions can post drafts but cannot run Socket Mode; a hosted webhook replaces the local Mac listener.

Files touched:
- `src/peachtree_blog/slack_webhook/`
- `src/peachtree_blog/generated_store.py`
- `src/peachtree_blog/draft_approval.py`
- `src/peachtree_blog/paths.py`
- `scripts/archive_ci_draft.py`
- `.github/workflows/weekly.yml`
- `.gitignore`
- `generated/slack_index.json`
- `webhook/Dockerfile`
- `webhook/docker-compose.yml`
- `requirements-webhook.txt`
- `docs/slack-webhook-setup.md`
- `docs/github-actions.md`
- `.env.template`
- `CHANGELOG.md`

Tested:
- Not run (deploy + Slack URL verification required).

Notes / next step:
- Deploy webhook per `docs/slack-webhook-setup.md`, set Slack Request URL, run weekly workflow once to populate `generated/`.

## 2026-06-11 - Move PSAI api_url and author to config/psai.json

Changed:
- Added `config/psai.json` for non-secret PSAI settings (api_url, author, default_status, etc.).
- `post.py` loads from that file; only `PSAI_API_KEY` required in `.env` / GitHub Secrets.
- Updated workflows, `.env.template`, README, and `docs/github-actions.md`.

Why:
- API URL and author email are not secrets; keeping them in repo config avoids duplicate GitHub Secrets.

Files touched:
- `config/psai.json`
- `src/peachtree_blog/post.py`
- `src/peachtree_blog/pipeline/approve_listen.py`
- `.env.template`
- `.github/workflows/weekly.yml`
- `.github/workflows/publish.yml`
- `.github/workflows/approve.yml`
- `README.md`
- `docs/github-actions.md`
- `CHANGELOG.md`

Tested:
- Not run.

Notes / next step:
- Remove `PSAI_API_URL` and `PSAI_AUTHOR` from local `.env` if still present; edit `config/psai.json` instead.

## 2026-06-11 - Add GitHub Actions automation workflows and setup doc

Changed:
- `.github/workflows/weekly.yml`: search → evaluate → write on schedule (Mon 8 AM ET) or manual dispatch; optional Slack post; draft artifacts.
- `.github/workflows/publish.yml`: manual PSAI publish workflow.
- `.github/workflows/approve.yml`: fixed args/env; legacy alias for publish.
- `docs/github-actions.md`: secrets checklist, architecture, local listener requirement, workflow-scope push note.
- `README.md`: link to GitHub Actions doc.

Why:
- Start automating weekly draft generation while Slack approval and PSAI publish remain partially local until Spectrum platform migration completes.

Files touched:
- `.github/workflows/weekly.yml`
- `.github/workflows/publish.yml`
- `.github/workflows/approve.yml`
- `docs/github-actions.md`
- `README.md`
- `CHANGELOG.md`

Tested:
- Not run (workflow YAML only — test via Actions → Run workflow after secrets are set).

Notes / next step:
- Add repository secrets from `docs/github-actions.md`, push with `workflow` scope, run Weekly Blog Pipeline manually once.

## 2026-06-10 - Slack notice when approval listener stops (e + Enter)

Changed:
- `approve_listen.py`: typing `e` + Enter to stop listening posts a thread reply on the active approval message warning that reactions/feedback are paused until the listener runs again.

Why:
- Reviewers should know when the terminal listener is no longer processing Slack events.

Files touched:
- `src/peachtree_blog/pipeline/approve_listen.py`
- `CHANGELOG.md`

Tested:
- Not run (Slack UI change only).

Notes / next step:
- Restart `approve_listen` and press `e` to verify the thread reply.

## 2026-06-10 - Cap PSAI social description at 150 characters

Changed:
- `post.py`: `social.description` now truncated to 150 chars (PSAI `share-desc` limit); `meta.meta_description` stays at 160.

Why:
- Live publish returned HTTP 400: "Sharing Description Must Be No More Than 150 Characters".

Files touched:
- `src/peachtree_blog/post.py`
- `CHANGELOG.md`

Tested:
- Not run (validation limit fix).

Notes / next step:
- Re-approve and react 🌐 to retry publish.

## 2026-06-10 - Fix PSAI blogId response parsing and API logging

Changed:
- `post.py`: read `blogId` (camelCase) from PSAI 201 responses via `_get_blog_id()`; audit trail and Slack success text now work.
- `post.py`: URL extraction checks `url`, `blogUrl`, `blog_url`, and legacy keys; debug-logs response keys when missing.
- `post.py`: request logging (endpoint, title, status, author) and error logging on failure; timeout 30s.
- `post.py`: parse `requestId` from error responses.
- `.env.template` / `README.md`: document confirmed base URL `https://developers.predictivesalesai.com`.

Why:
- Swagger confirms PSAI returns `blogId`, not `blog_id`; silent None broke duplicate detection and success messages.

Files touched:
- `src/peachtree_blog/post.py`
- `.env.template`
- `README.md`
- `CHANGELOG.md`

Tested:
- `python -m py_compile src/peachtree_blog/post.py`

Notes / next step:
- Set `PSAI_API_URL=https://developers.predictivesalesai.com` and `PSAI_AUTHOR` to your PSAI login email, then `--dry-run` before live post.

## 2026-06-10 - Pre-add globe Slack reaction for website publish

Changed:
- `approve_listen.py`: bot now adds `:globe_with_meridians:` alongside checkmark/x/repeat when PSAI is configured (and auto-publish is off); intro text mentions it.
- `post.py`: post-approval reminder says to click the pre-added globe reaction.

Why:
- Reviewers should not have to search Slack's emoji picker to publish an approved draft.

Files touched:
- `src/peachtree_blog/pipeline/approve_listen.py`
- `src/peachtree_blog/post.py`
- `CHANGELOG.md`

Tested:
- Not run (Slack UI change only).

Notes / next step:
- Post a new draft to Slack to see the fourth reaction; existing messages keep their old reactions.

## 2026-06-10 - Implement PSAI website publish after Slack approval

Changed:
- `src/peachtree_blog/post.py`: full Predictive Sales AI client for `POST /v1/blogs` (Markdown → HTML, meta/categories/tags, CLI, dry-run).
- `src/peachtree_blog/draft_pdf.py`: shared `markdown_body_to_html()` for CMS body HTML.
- `src/peachtree_blog/pipeline/approve_listen.py`: after approval, offer `:globe_with_meridians:` reaction to publish; optional `PSAI_AUTO_PUBLISH=true` for immediate post.
- `.env.template`: PSAI API key, URL, author, status, and publish toggles.
- `.github/workflows/approve.yml`: pass draft path and decision into `post.py`.
- `README.md`: website publishing section.

Why:
- Approved drafts should be publishable to the company website via Spectrum Predictive Sales AI without manual copy-paste.

Files touched:
- `src/peachtree_blog/post.py`
- `src/peachtree_blog/draft_pdf.py`
- `src/peachtree_blog/pipeline/approve_listen.py`
- `.env.template`
- `.github/workflows/approve.yml`
- `README.md`
- `CHANGELOG.md`

Tested:
- `python -m py_compile` on modified modules.

Notes / next step:
- Add `PSAI_API_KEY`, `PSAI_API_URL`, and `PSAI_AUTHOR` to `.env` and GitHub secrets; set `PSAI_DEFAULT_STATUS=published` when ready to go live.

## 2026-06-09 - Shift blog prompt from SEO to GEO: quality gates over count floors

Changed:
- `prompts/blog.txt`: removed 800–1,200 word count floor; replaced with "write as long as content requires."
- `prompts/blog.txt`: removed "each H2 must contain a Metro Atlanta location" keyword rule; location in heading only when it makes the question more precise.
- `prompts/blog.txt`: replaced "4+ neighborhoods" hard count with a quality gate — name a location only when a concrete specific reason attaches to it.
- `prompts/blog.txt`: removed "include named Metro Atlanta locations in the table where possible" — location column only when it genuinely changes the answer.
- `prompts/blog.txt`: renamed Section 5 from STATISTICS to CITATIONS; reframed as "cite every citable fact" rather than hitting a count; aim 3–5 but fewer or more is valid.
- `prompts/blog.txt`: Section 6 (locations) now leads with the quality rule, not the count floor.
- `prompts/blog.txt`: validation checklist and STEP 2 audit updated to match relaxed citation and location guidance.
- `write_common.py`: citation validation widened from `3 <= n <= 5` to `2 <= n <= 6`; check renamed `citation_count_2_to_6`.
- `write_common.py`: all retry-feedback and checklist strings updated to match.

Why:
- Hard SEO-style count floors (word count, location count, citation count) were pushing the model to pad copy, name-drop locations without reason, and invent statistics to hit a number — all of which hurt GEO signal. GEO rewards specificity and quotability, not volume.

Files touched:
- `prompts/blog.txt`
- `src/peachtree_blog/write_common.py`
- `CHANGELOG.md`

Tested:
- Not run (prompt/validation change only — re-run write to regenerate draft).

Notes / next step:
- Re-run write on kept sources; watch validation JSON for citation_count_2_to_6 and location quality on the next draft.

## 2026-06-09 - Prompt table/FAQ/location guidance from 152847 vs 145848 review

Changed:
- `prompts/blog.txt`: prefer location × housing-type × scenario tables; construction-era location detail; varied insurance FAQ topics; named storms only from SOURCES.
- `feedback/style_notes.txt`: logged publishable patterns from draft 152847 and table/FAQ borrowings from 145848.

Why:
- 152847 fixed brand/CTA/bridge issues; Claude review flagged weaker table format and repetitive FAQ vs older draft.

Files touched:
- `prompts/blog.txt`
- `feedback/style_notes.txt`
- `CHANGELOG.md`

Tested:
- Not run.

Notes / next step:
- 152847 is publishable as-is; next write should produce stronger scenario tables and FAQ variety.

## 2026-06-09 - pipeline.py --default uses Qwen3.5 397B for write/rewrite

Changed:
- `python pipeline.py --default` sets Qwen3.5 397B as write and Slack rewrite model without the interactive model menu.
- Model picker marks Qwen3.5 397B with `(default)`; Enter selects it.

Why:
- Prefer strongest instruction-following model for routine pipeline runs without re-picking each session.

Files touched:
- `src/peachtree_blog/pipeline/write_serverless.py`
- `src/peachtree_blog/pipeline/cli.py`
- `src/peachtree_blog/pipeline/runner.py`
- `pipeline.py`
- `CHANGELOG.md`

Tested:
- `python -m py_compile` on modified modules.

Notes / next step:
- Use `python pipeline.py --default` (double dash). Model menu still available without the flag.

## 2026-06-09 - Blog prompt fixes from draft 145848 review

Changed:
- `prompts/blog.txt`: Peachtree as authority (not vendor brands), linked citations, 3+ CTAs, insurance-to-roof bridge section.
- `write_common.py`: validation for linked citations, min 3 CTAs, no competitor brand voice, roof-service bridge signals; vendor press-release hints in sources block.
- `feedback/style_notes.txt`: editor notes from Claude review of wind-driven rain draft.

Why:
- Draft 145848 centered StormArmour, used weak single CTA, unlinked citations, and under-connected insurance content to roof replacement.

Files touched:
- `prompts/blog.txt`
- `src/peachtree_blog/write_common.py`
- `feedback/style_notes.txt`
- `CHANGELOG.md`

Tested:
- Not run (prompt/validation only — re-run write to regenerate draft).

Notes / next step:
- Re-run write on kept sources or `:repeat:` to produce a publishable revision.

## 2026-06-09 - Incremental search+evaluate with early Tavily exit

Changed:
- Search evaluates each keyword-qualified source immediately via `IncrementalEvaluator`; stops Tavily after 2 sources score `>= 6.0` (default on).
- Pipeline restart is now two stages: `search --incremental-evaluate` → write (standalone `evaluate` remains for menu/CLI re-runs).
- Flags: `--incremental-evaluate` / `--no-incremental-evaluate`, `--min-evaluated-kept`, `--evaluate-model`.

Why:
- Avoid burning Tavily credits after enough write-ready sources are found; fail faster when candidates score poorly.

Files touched:
- `src/peachtree_blog/pipeline/evaluate.py`
- `src/peachtree_blog/pipeline/search.py`
- `src/peachtree_blog/pipeline/runner.py`
- `src/peachtree_blog/pipeline/cli.py`
- `CHANGELOG.md`

Tested:
- `python -m py_compile` on modified modules.

Notes / next step:
- Menu option 2 (Evaluate) still re-scores `search_results.json` if you ran search with `--no-incremental-evaluate`.

## 2026-06-09 - Expand search depth with longer multi-stage lookback

Changed:
- Added `priority_21_day_news`, `secondary_30_day_news`, and `georgia_roofing_trade_21_day` stages; broad stage extended to 21 days (8 stages total).
- Fixed bug where every stage was forced to 7-day Tavily/recency — each stage now uses its own lookback capped by `--max-age-days` (default 21).
- Raised defaults: 100 Tavily credits (was 50), 3 queries/cluster (was 2), 8 results/query, 21-day recency cap.

Why:
- Tighter geography filters returned 0 sources; need more API coverage across Atlanta TV, county papers, and GA insurance/trade outlets.

Files touched:
- `src/peachtree_blog/pipeline/search.py`
- `CHANGELOG.md`

Tested:
- `python -m py_compile` on `search.py`.

Notes / next step:
- Full 8-stage run uses ~96 credits at 6 active queries; use `--all-queries` or `--max-credits 150` for even wider sweeps.

## 2026-06-09 - Tighten search geography and roofing relevance gates

Changed:
- Search requires Metro Atlanta / Georgia signals in headline or article lead (not job-listing footers).
- Rejects out-of-state headlines, national `/news/west/` paths, crime/health headlines, and metro TV stories without roofing in the title.
- Primary roofing signals no longer treat standalone `insurance`/`claim` in sidebars as sufficient; insurance phrases must be explicit (`homeowners insurance`, `roof insurance`, etc.).

Why:
- Colorado insurance, WSB crime stories, and sidebar false positives passed keyword search despite zero Georgia roofing relevance.

Files touched:
- `src/peachtree_blog/pipeline/search.py`
- `CHANGELOG.md`

Tested:
- `python -m py_compile` on `search.py`.

Notes / next step:
- Re-run search; quiet weeks may still return few results after `used_sources.json` blocks prior URLs.

## 2026-06-09 - Full pipeline menu option in pipeline.py

Changed:
- Interactive `pipeline.py` menu adds option 5: full pipeline (search → evaluate → write → post to Slack → listen).

Why:
- Run the entire workflow from one CLI choice without stepping through each stage manually.

Files touched:
- `src/peachtree_blog/pipeline/cli.py`
- `CHANGELOG.md`

Tested:
- Not run.

Notes / next step:
- Restart `python pipeline.py` to see the new menu item (option 6 is Exit).

## 2026-06-09 - Live terminal output on Slack pipeline restart

Changed:
- Slack `:repeat:` restart runs on the main CLI listen thread (not a background thread) so subprocess output streams in the same terminal.
- `run_pipeline_restart` prints stage banners (1/3 Search, 2/3 Evaluate, 3/3 Write) with flushed, unbuffered child processes (`python -u`, `PYTHONUNBUFFERED=1`).

Why:
- User could not see which pipeline stage was running live when reacting with :repeat: in Slack.

Files touched:
- `src/peachtree_blog/pipeline/runner.py`
- `src/peachtree_blog/pipeline/approve_listen.py`
- `CHANGELOG.md`

Tested:
- `python -m py_compile` on modified modules.

Notes / next step:
- Restart `python pipeline.py` approve listen session to pick up changes.

## 2026-06-09 - Block junk sources on pipeline restart

Changed:
- Search now requires a core roofing signal term and rejects off-topic local news (senior health, crime) without roofing context.
- Evaluate no longer promotes sub-threshold sources via minimum-kept fallback; exits non-zero when zero sources qualify.
- Slack `:repeat:` restart passes the recycled draft's strategy cluster to search and rotates query week for fresher results.

Why:
- Repeat produced an irrelevant roof-safety draft from a senior blood-pressure article after insurance URLs were blocked in `used_sources.json`.

Files touched:
- `src/peachtree_blog/pipeline/search.py`
- `src/peachtree_blog/pipeline/evaluate.py`
- `src/peachtree_blog/pipeline/runner.py`
- `src/peachtree_blog/pipeline/approve_listen.py`
- `CHANGELOG.md`

Tested:
- Not run (requires Tavily/Together API keys).

Notes / next step:
- If restart fails with "No sources met quality thresholds", wait for new local roofing news or temporarily use `--include-used-sources` on search.

## 2026-06-08 - Slack clear-channel command for bot messages

Changed:
- Added `approve_listen clear-channel` with `--dry-run` and `--yes` to delete all bot-authored messages in `SLACK_APPROVAL_CHANNEL` (roots and thread replies).

Why:
- Clean up old approval threads without manual Slack housekeeping.

Files touched:
- `src/peachtree_blog/pipeline/approve_listen.py`
- `README.md`
- `CHANGELOG.md`

Tested:
- Not run (requires live Slack token).

## 2026-06-08 - Approval metadata in validation JSON; approved drafts folder

Changed:
- Slack approval state now lives in an `approval` object inside each `drafts_json/*-validation.json` (no separate `output/approvals/*.json` per draft).
- On ✅ approval, draft artifacts move from `output/drafts/` to `output/approved/` (same `drafts_md/`, `drafts_pdf/`, `drafts_json/` layout).
- Added `src/peachtree_blog/draft_approval.py` for validation lookup, relocation, and legacy approval migration.
- `--feedback-json` for rewrites now points at a validation JSON file.

Why:
- Single source of truth per draft; approved blogs archived under `output/approved/`.

Files touched:
- `src/peachtree_blog/draft_approval.py` (new)
- `src/peachtree_blog/pipeline/approve_listen.py`
- `src/peachtree_blog/write_common.py`
- `src/peachtree_blog/pipeline/write_serverless.py`
- `src/peachtree_blog/paths.py`
- `README.md`
- `CHANGELOG.md`

Tested:
- `py_compile` on modified modules.

Notes / next step:
- Legacy `output/approvals/*.json` files auto-migrate on the next Slack reaction lookup.

## 2026-06-08 - Use repeat emoji for pipeline restart

Changed:
- Pipeline restart Slack reaction uses `:repeat:` (🔁), not `:recycling_symbol:` or `:repeat_one:`.

Why:
- User preference for the standard repeat emoji.

Files touched:
- `src/peachtree_blog/pipeline/approve_listen.py`
- `README.md`
- `CHANGELOG.md`

Tested:
- Not run (emoji name change only).

## 2026-06-08 - Slack recycle reaction reruns full pipeline

Changed:
- Reacting with `:repeat:` on an approval message runs search → evaluate → write (`--clear-drafts`) in the background, then posts a new draft to Slack.
- Added `run_pipeline_restart()` in `runner.py`; `cli.py --all` now uses it.
- Approval intro and bot prompt reactions document the recycle option.

Why:
- Unusable drafts should restart from fresh sources, not only thread rewrites.

Files touched:
- `src/peachtree_blog/pipeline/approve_listen.py`
- `src/peachtree_blog/pipeline/runner.py`
- `src/peachtree_blog/pipeline/cli.py`
- `README.md`
- `CHANGELOG.md`

Tested:
- `py_compile` on modified modules.

Notes / next step:
- Repeat restart is blocked while a restart is in progress or after approval; uses the same write model as the discarded draft when available.

## 2026-06-08 - Record used sources only on Slack approval

Changed:
- Removed `record_used_sources()` call from `save_draft_outputs()` in `write_common.py` — writing a draft no longer blocks its URLs in search.
- On first Slack ✅ approval, `approve_listen.py` reads `sources_used` from the draft validation JSON and records them in `used_sources.json`.
- Added `record_used_sources_from_validation_report()` and `--seed-validation` CLI backfill in `used_sources.py`.

Why:
- Source URLs should be reserved for published/approved blogs, not every draft attempt.

Files touched:
- `src/peachtree_blog/write_common.py`
- `src/peachtree_blog/pipeline/approve_listen.py`
- `src/peachtree_blog/used_sources.py`
- `src/peachtree_blog/pipeline/evaluate.py`
- `README.md`
- `CHANGELOG.md`

Tested:
- Not run.

Notes / next step:
- Already-approved drafts (e.g. `111923`) were not auto-backfilled; re-approve in Slack or seed from validation JSON if those URLs should block search now.

## 2026-06-08 - Add silent accuracy self-audit to blog prompt

Changed:
- Added mandatory five-step `ACCURACY SELF-AUDIT` section to `prompts/blog.txt` — source grounding, citation integrity, story-type match, location quality, final read-through; output only the corrected post, never the audit.
- Capped allowlist location guidance at 6–12 names with depth over laundry lists.
- Mirrored silent re-read rule in `build_first_draft_prompt()` runtime source-use rules.

Why:
- Draft `125930` improved accuracy but under-cited and stuffed 33 locations; models need an explicit post-draft fact-check pass without leaking chain-of-thought.

Files touched:
- `prompts/blog.txt`
- `src/peachtree_blog/write_common.py`
- `CHANGELOG.md`

Tested:
- Not run (prompt-only change).

Notes / next step:
- Re-run write on the insurance cluster and confirm citation count and location count stay in range.

## 2026-06-08 - Legal accuracy guardrails and location allowlist sync

Changed:
- Added `FACTUAL ACCURACY RULE` to `prompts/blog.txt` — no invented case names, legislation, or unrelated exclusion types; neutral insurer language; multi-outlet citation spread.
- Injected `{metro_locations_list}` into the write prompt from `METRO_LOCATIONS` so the model and validator use the same allowlist.
- Expanded `METRO_LOCATIONS` (Brookhaven, Duluth, Lithonia, Kennesaw, Johns Creek, Suwanee, etc.).
- Strengthened runtime source-use rules in `build_first_draft_prompt()` and validation retry hints.

Why:
- Draft `125010` hallucinated firearms exclusions, Carmichael rulings, and tort reform 2025; it also failed `location_count_at_least_6` because neighborhood names were outside the validator allowlist.

Files touched:
- `prompts/blog.txt`
- `src/peachtree_blog/write_common.py`
- `CHANGELOG.md`

Tested:
- Not run (prompt and validation-list change).

Notes / next step:
- Re-run write on the insurance cluster; prefer Draft 1 (`111923`) for publish with Draft 2's before/after table format as a manual merge.

## 2026-06-05 - Refine blog.txt for GEO over SEO

Changed:
- Rewrote `prompts/blog.txt` with GEO principles, cluster-based angles, conditional storm/insurance sections, citable-chunk H2 format, stronger citation anti-hallucination rules, and improved FAQ guidance.
- Replaced visible pre-write checklist with silent planning instruction to reduce chain-of-thought leaks.

Why:
- Drafts were over-fitting a storm template (historical weather, April–September) on non-storm stories; GEO quality needs source-grounded, extractable answers matched to story type.

Files touched:
- `prompts/blog.txt`
- `CHANGELOG.md`

Tested:
- Not run (prompt-only change).

Notes / next step:
- Run write on insurance and storm clusters to compare draft quality; promote recurring Slack feedback into `feedback/style_notes.txt`.

## 2026-06-05 - Slack posts show feedback rewrite model

Changed:
- Initial approval posts include a *Slack feedback rewrites* block with the Together model chosen for thread feedback auto-rewrites.
- Revision posts label generation stats under *Rewrite* with `Rewrite model:` instead of generic `Model:`.

Why:
- Reviewers should see which model will handle feedback rewrites without checking the CLI.

Files touched:
- `src/peachtree_blog/pipeline/approve_listen.py`
- `src/peachtree_blog/write_common.py`
- `CHANGELOG.md`

Tested:
- Not run (Slack message formatting only).

Notes / next step:
- Post a draft via approve (option 4) and confirm the rewrite model appears below *Generation*.

## 2026-06-05 - Fix black-box dashes in draft PDFs

Changed:
- `draft_pdf.normalize_text_for_pdf()` maps Unicode hyphen/dash characters (non-breaking hyphen, en dash, em dash, etc.) to ASCII `-` before xhtml2pdf runs.

Why:
- Helvetica in xhtml2pdf lacks glyphs for LLM-style `‑` and `—`, which showed as black boxes in Slack PDFs.

Files touched:
- `src/peachtree_blog/draft_pdf.py`
- `CHANGELOG.md`

Tested:
- Not run (font normalization only).

Notes / next step:
- Re-run write or regenerate PDF from existing `.md` to refresh `drafts_pdf/` files.

## 2026-06-05 - Slack approval posts include generation cost summary

Changed:
- `approve_listen` reads each draft's `*-validation.json` and adds a *Generation* block to the Slack post: model, time, tokens, estimated USD cost, validation attempt, revision mode, and source count.

Why:
- Reviewers can see what a draft cost to produce without opening validation JSON.

Files touched:
- `src/peachtree_blog/pipeline/approve_listen.py`
- `src/peachtree_blog/write_common.py`
- `CHANGELOG.md`

Tested:
- Not run (Slack message formatting only).

Notes / next step:
- Post a draft to Slack and confirm the generation block appears under the file paths.

## 2026-06-05 - Disable Qwen3.5 thinking mode for blog drafts

Changed:
- `generate_with_together()` passes `reasoning={"enabled": False}` and `chat_template_kwargs={"enable_thinking": False}` for hybrid models such as `Qwen/Qwen3.5-397B-A17B`.
- Added `extract_markdown_draft()` to drop leaked thinking preambles and keep content from the first `#` H1 onward.
- Raises a clear error if the model still returns planning text with no Markdown draft.

Why:
- Qwen3.5 defaults to thinking mode and was saving a “Thinking Process” plan instead of the article, failing validation.

Files touched:
- `src/peachtree_blog/write_common.py`
- `CHANGELOG.md`

Tested:
- Not run (Together API behavior change).

Notes / next step:
- Re-run write with menu option 1 (Qwen3.5 397B) and confirm validation passes.

## 2026-06-05 - Enable in-editor PDF preview for draft PDFs

Changed:
- Added `.vscode/extensions.json` recommending `tomoki1207.pdf` (Cursor/OpenVSX) and workspace PDF preview settings.
- Allow committing `.vscode/extensions.json` and `.vscode/settings.json` via `.gitignore` exception.

Why:
- `output/drafts/drafts_pdf/*.pdf` are valid PDFs but Cursor opens them as raw text without a PDF viewer extension.

Files touched:
- `.vscode/extensions.json`
- `.vscode/settings.json`
- `.gitignore`
- `CHANGELOG.md`

Tested:
- Not run (editor configuration only).

Notes / next step:
- Install the recommended extension when Cursor prompts, then reopen a draft PDF.

## 2026-06-05 - Order write model menu by size (largest first)

Changed:
- `SERVERLESS_MODEL_CHOICES` in `write_serverless.py` is now 397B → 235B → 120B → 70B; default model unchanged (`Qwen3 235B tput`, menu option 2).

Why:
- Show largest models at the top when picking a writer at the terminal.

Files touched:
- `src/peachtree_blog/pipeline/write_serverless.py`
- `CHANGELOG.md`

Tested:
- Not run (menu order only).

Notes / next step:
- `--model` menu numbers: 397B = 1, 235B default = 2, 120B = 3, 70B = 4.

## 2026-06-05 - Remove all mock modes

Changed:
- Removed `--mock`, `generate_mock_draft`, and local template drafting from `write_serverless.py`; write always calls Together AI.
- Removed mock prompts/flags from `cli.py` and `approve_listen.py`; dropped unused `mode` arg on `record_used_sources`.
- Evaluate and write both require `TOGETHER_API_KEY`; removed mock docs from `README.md`.

Why:
- Production pipeline should always use real Together scoring and drafting.

Files touched:
- `src/peachtree_blog/pipeline/write_serverless.py`
- `src/peachtree_blog/pipeline/cli.py`
- `src/peachtree_blog/pipeline/approve_listen.py`
- `src/peachtree_blog/write_common.py`
- `src/peachtree_blog/used_sources.py`
- `README.md`
- `CHANGELOG.md`

Tested:
- Not run (flag and dead-code removal).

Notes / next step:
- Ensure `TOGETHER_API_KEY` is set before evaluate or write runs.

## 2026-06-05 - Remove evaluate mock mode

Changed:
- Dropped `--mock` and local heuristic scoring from `evaluate.py`; evaluation always calls Together AI.
- Interactive menu and `pipeline.py --all` no longer offer or pass mock mode for evaluate (write mock unchanged).
- Removed evaluate `--mock` docs from `README.md`.

Why:
- Evaluate should always use real Together scoring in normal workflow.

Files touched:
- `src/peachtree_blog/pipeline/evaluate.py`
- `src/peachtree_blog/pipeline/cli.py`
- `README.md`
- `CHANGELOG.md`

Tested:
- Not run (flag removal and dead-code cleanup).

Notes / next step:
- Ensure `TOGETHER_API_KEY` is set before running evaluate.

## 2026-06-05 - Interactive pipeline menu loops after each stage

Changed:
- `run_interactive_menu()` returns to the stage picker automatically after search, evaluate, write, or approve finish; only option 5 (Exit) quits.
- Removed the post-stage `Run another stage? [y/N]` prompt.

Why:
- Keep `pipeline.py` open for back-to-back runs without restarting the script.

Files touched:
- `src/peachtree_blog/pipeline/cli.py`
- `CHANGELOG.md`

Tested:
- Not run (menu flow change only).

Notes / next step:
- Run `python pipeline.py`, complete a stage, confirm the menu reappears.

## 2026-06-04 - Evaluate stage prints model and token cost summary

Changed:
- `evaluate.py` accumulates Together token usage across all source scores and prints model, timing, tokens, and estimated USD cost via `print_generation_cost_summary` (same helper as `write_serverless`).
- Logs evaluation model at start (`--mock` vs live model ID).

Why:
- Match write-stage visibility when scoring sources so evaluation spend is obvious per run.

Files touched:
- `src/peachtree_blog/pipeline/evaluate.py`
- `CHANGELOG.md`

Tested:
- `python -m peachtree_blog.pipeline.evaluate --mock` — cost summary shows mock / elapsed time.

Notes / next step:
- Live Together run shows per-source API call count in the timing line.

## 2026-06-04 - Remove legacy approve/search/write/evaluate package dirs

Changed:
- Deleted empty `src/peachtree_blog/{approve,search,write,evaluate}/` leftovers from pre-pipeline layout.
- `pipeline.py` calls `remove_legacy_package_dirs()` on startup so those folders are not left behind.
- Subprocess env sets `PYTHONPYCACHEPREFIX` explicitly (only `src/__pycache__/` for bytecode).

Files touched:
- `src/peachtree_blog/paths.py`, `pipeline.py`, `pipeline/runner.py`, `CHANGELOG.md`

Tested:
- `python pipeline.py --help` — only `pipeline/`, `tools/`, and `src/__pycache__/` remain.

## 2026-06-04 - Centralize Python bytecode cache under src/__pycache__/

Changed:
- `configure_bytecode_cache()` in `paths.py` sets `PYTHONPYCACHEPREFIX` to `src/__pycache__/` (auto-runs on import).
- Pipeline entry points and subprocess env use the same setting; `.gitignore` includes `src/__pycache__/`.
- Removed stale `evaluate/`, `search/`, etc. folders that only held old `__pycache__`.

Why:
- Avoid many `__pycache__` directories beside each package folder.

Files touched:
- `src/peachtree_blog/paths.py`, `pipeline.py`, `pipeline/runner.py`, `.gitignore`, scripts

Tested:
- After `python pipeline.py --help`, only `src/__pycache__/` exists (no per-package `__pycache__`).

Notes / next step:
- Safe to delete `src/__pycache__/` anytime; set `PEACHTREE_DISABLE_CENTRAL_PYCACHE=1` to restore default Python behavior.

## 2026-06-04 - Move pipeline stages into src/peachtree_blog/pipeline/

Changed:
- Moved `search.py`, `evaluate.py`, `write_serverless.py`, `approve_listen.py` into `src/peachtree_blog/pipeline/`.
- Moved `pipeline_cli.py` → `pipeline/cli.py`, `cli_runner.py` → `pipeline/runner.py`.
- Updated module paths (`peachtree_blog.pipeline.*`), root `pipeline.py`, scripts, README.

Why:
- Keep all stage scripts in one directory instead of separate search/evaluate/write/approve folders.

Files touched:
- `src/peachtree_blog/pipeline/` (new layout)
- Removed empty `search/`, `evaluate/`, `write/`, `approve/` packages
- `pipeline.py`, `pyproject.toml`, `README.md`, scripts, `write_common.py`, `CHANGELOG.md`

Tested:
- `python pipeline.py --help`, `python -m peachtree_blog.pipeline.search --help`

## 2026-06-04 - Merge write.py into standalone write_serverless.py

Changed:
- Moved dedicated-endpoint generation into `write_serverless.py` behind `--dedicated-endpoint`; deleted `write.py`.
- Default runs stay serverless (model menu); pipeline unchanged.
- `scripts/write_with_endpoint.sh` calls `write_serverless --dedicated-endpoint`.
- Removed `write` module key from `cli_runner`.

Why:
- Single writer module; same pattern as approve_listen consolidation.

Files touched:
- `src/peachtree_blog/write/write_serverless.py` (deleted `write.py`)
- `src/peachtree_blog/cli_runner.py`, `write_common.py`, `together_endpoint.py`, scripts, `CHANGELOG.md`

Tested:
- `python -m py_compile` on `write_serverless.py`.

## 2026-06-04 - Merge approve.py into standalone approve_listen.py

Changed:
- Moved all Slack post/listen/rewrite logic into `approve_listen.py`; deleted `approve.py`.
- CLI: default run posts latest + listens; subcommands `post` and `listen` retained.
- `cli_runner` and pipeline use only `peachtree_blog.approve.approve_listen`.

Why:
- Single approval module; no parent/child split between approve and approve_listen.

Files touched:
- `src/peachtree_blog/approve/approve_listen.py` (deleted `approve.py`)
- `src/peachtree_blog/cli_runner.py`, `pipeline_cli.py`, `README.md`, `CHANGELOG.md`

Tested:
- `python -m py_compile` on `approve_listen.py` and `pipeline_cli.py`.

## 2026-06-04 - Approve listen: type e to return to pipeline menu

Changed:
- `listen()` polls CLI stdin; typing `e` + Enter disconnects Slack Socket Mode and exits cleanly (no Ctrl+C).
- Pipeline menu runs approve in-process so exiting listen returns directly to stage selection.
- `approve_listen.run_approve_post_and_listen()` shared by CLI module and pipeline.

Why:
- Stay in one terminal session: approve → listen → `e` → pick search/evaluate/write again.

Files touched:
- `src/peachtree_blog/approve/approve.py`, `approve_listen.py`, `pipeline_cli.py`, `CHANGELOG.md`

Tested:
- Not run (requires Slack credentials and interactive terminal).

## 2026-06-04 - Remove package __init__.py files

Changed:
- Deleted all `__init__.py` under `src/peachtree_blog/` (namespace packages; no code used them).
- Set `namespaces = true` in `pyproject.toml` so `pip install -e .` still discovers packages.

Why:
- Files were docstring-only markers; `PROJECT_ROOT` is imported from `peachtree_blog.paths` everywhere.

Files touched:
- `src/peachtree_blog/**/__init__.py` (removed)
- `pyproject.toml`, `CHANGELOG.md`

Tested:
- `python pipeline.py --help`, `python -m peachtree_blog.search.search --help`, import smoke test.

## 2026-06-04 - Consolidate search into search.py only

Changed:
- Moved `search_all_roofing.py` implementation into `search.py` (broad roofing search, 50-credit cap, keyword match).
- Default search output: `output/sources/search_results.json` (evaluate default input updated).
- Removed `search_all_roofing.py`, `search_less_strict.py`, `search_strict.py`.
- Pipeline and `cli_runner` use single `search` module key; dropped `--search strict|less_strict`.

Why:
- One search entry point; pipeline menu and evaluate align on the same output file.

Files touched:
- `src/peachtree_blog/search/search.py`
- `src/peachtree_blog/cli_runner.py`, `src/peachtree_blog/pipeline_cli.py`
- `src/peachtree_blog/evaluate/evaluate.py`, `README.md`, `CHANGELOG.md`

Tested:
- `python -m peachtree_blog.search.search --help`

Notes / next step:
- Re-run search if you still have only `search_results_all_roofing.json` from older runs.

## 2026-06-04 - pipeline.py defaults to interactive stage menu

Changed:
- `python pipeline.py` now shows a numbered menu (Search, Evaluate, Write, Approve, Exit) instead of running the full pipeline.
- Full non-interactive run moved to `python pipeline.py --all` (GitHub Actions weekly workflow updated).

Why:
- Match local workflow: pick one stage at a time rather than auto-running search through write.

Files touched:
- `src/peachtree_blog/pipeline_cli.py`, `pipeline.py`, `.github/workflows/weekly.yml`, `README.md`, `CHANGELOG.md`

Tested:
- `python pipeline.py --help`

## 2026-06-04 - Pipeline from src; remove root CLI shims

Changed:
- Rebuilt `pipeline.py` to run stages via `python -m peachtree_blog.*` (`cli_runner.py`, `pipeline_cli.py`).
- Added `python pipeline.py --menu` interactive stage picker (search variants, evaluate, write, approve, clean, full pipeline).
- Added `python pipeline.py --stage` for single-stage runs; `peachtree-pipeline` console script after `pip install -e .`.
- Removed root shim files (`evaluate.py`, `write_serverless.py`, `search*.py`, `approve*.py`, `_entry.py`, etc.).
- Slack auto-rewrites invoke `peachtree_blog.write.write_serverless` via module subprocess with `PYTHONPATH=src`.

Why:
- One orchestrator and no duplicate entry points; real code lives only under `src/peachtree_blog/`.

Files touched:
- `pipeline.py`, `src/peachtree_blog/pipeline_cli.py`, `src/peachtree_blog/cli_runner.py`
- `src/peachtree_blog/approve/approve.py`
- `pyproject.toml`, `README.md`, `.github/workflows/weekly.yml`, `.github/workflows/approve.yml`
- Deleted root shims listed above
- `CHANGELOG.md`

Tested:
- `python pipeline.py --help`

Notes / next step:
- Use `python pipeline.py --menu` locally; update any personal scripts that called root `*.py` shims to `python -m` paths above.

## 2026-06-04 - GEO blog prompt v2 with Quick Answer block

Changed:
- Replaced `prompts/blog.txt` with stricter GEO template: pre-write checks, news-anchored opening, Quick Answer block, question-style H2 examples, neighborhood vulnerability section, historical storm reference, FAQ 3–5 sentences.
- Updated `validate_draft()` to count opening words before the Quick Answer block only; added `has_quick_answer_block` automated check.
- Aligned retry checklist and validation hints in `write_common.py`.

Why:
- Improve AI-citable structure and reduce mismatch between prompt and automated validation (Quick Answer was inflating opening word count).

Files touched:
- `prompts/blog.txt`
- `src/peachtree_blog/write_common.py`
- `CHANGELOG.md`

Tested:
- Not run (prompt/validation change only).

Notes / next step:
- First draft may need 2–3 validation passes until the model reliably hits Quick Answer + 8 FAQs; watch `*-validation.json` for new failures.

## 2026-06-04 - Add GPT-OSS 120B to write_serverless and approve_listen model menu

Changed:
- Added `openai/gpt-oss-120b` as menu option 4 for `write_serverless.py` and `approve_listen.py` (shared `SERVERLESS_MODEL_CHOICES`).
- Added Together catalog pricing for GPT-OSS 120B in `write_common.py` cost summary.

Why:
- Gives a budget-friendly 120B-class alternative for A/B testing against Qwen 235B tput.

Files touched:
- `src/peachtree_blog/write/write_serverless.py`
- `src/peachtree_blog/write_common.py`
- `CHANGELOG.md`

## 2026-06-04 - Default serverless writer model to Qwen3 235B tput

Changed:
- `write_serverless` menu option 1 and `DEFAULT_SERVERLESS_MODEL` are now `Qwen/Qwen3-235B-A22B-Instruct-2507-tput` (397B is option 2).
- `approve_listen.py` inherits the same default via `resolve_writing_model()` (non-interactive and `--model` omitted).

Why:
- Prefer faster, lower-cost throughput model for routine drafts and Slack rewrites.

Files touched:
- `src/peachtree_blog/write/write_serverless.py`
- `src/peachtree_blog/approve/approve_listen.py`
- `CHANGELOG.md`

## 2026-06-04 - Fix approve_listen rewrite_model TypeError

Changed:
- Restored `rewrite_model` on `listen()`, `handle_message()`, and `regenerate_from_feedback()` in `approve.py` (passes `--model` to `write_serverless.py` on Slack auto-rewrite).

Why:
- `approve_listen.py` passed `rewrite_model=` after the src move, but `approve.py` had been restored from git without that parameter — posting to Slack succeeded, then `listen()` crashed.

Files touched:
- `src/peachtree_blog/approve/approve.py`
- `CHANGELOG.md`

Tested:
- Verified `listen` accepts `rewrite_model` keyword via import inspect

## 2026-06-04 - Restore detailed Together cost summary in write_serverless logs

Changed:
- Added `print_generation_cost_summary()` in `write_common.py` — prints model, elapsed time, API call count, token in/out/total, and estimated USD (input/output breakdown).
- `save_draft_outputs()` uses the helper again after each run (including multi-attempt validation retries).
- Added Together catalog pricing for `Qwen/Qwen3-235B-A22B-Instruct-2507-tput`.

Why:
- Terminal summary had regressed to minimal output when pricing was missing or fields were sparse; reviewers want token and dollar visibility like before.

Files touched:
- `src/peachtree_blog/write_common.py`
- `CHANGELOG.md`

Tested:
- Python syntax check on `write_common.py`

## 2026-06-04 - Reorganize application code under src/peachtree_blog

Changed:
- Moved Python modules into `src/peachtree_blog/` with subpackages: `search/`, `evaluate/`, `write/`, `approve/`, `tools/`.
- Added `paths.py` for repo-root paths (`PROJECT_ROOT`, `prompts/`, `output/`, etc.).
- Root-level `*.py` files are thin CLI shims via `_entry.py` (same commands as before: `python write_serverless.py`, etc.).
- Added `pyproject.toml` for optional editable install (`pip install -e .`).
- Updated `pipeline.py` to default search stage to `search_all_roofing.py` with `--search strict|less_strict` override.
- Restored and relocated modules that had been deleted locally (`write_common.py`, `approve.py`, `write.py`, search variants).

Why:
- Cleaner project layout as the pipeline grows; keeps data (`output/`, `prompts/`) at repo root.

Files touched:
- `src/peachtree_blog/**`
- `_entry.py`, `pyproject.toml`, `pipeline.py`, root CLI shims
- `README.md`
- `CHANGELOG.md`

Tested:
- `python -m py_compile` on shims and package imports
- `python write_serverless.py --help`, `python search_all_roofing.py --help`

## 2026-06-04 - Unified serverless writer model menu and approval rewrite wiring

Changed:
- `write_serverless.py` prompts for model choice (Qwen3.5 397B, Llama 3.3 70B, Qwen3 235B tput) or accepts `--model` / menu number.
- Slack rewrites inherit model from prior draft `*-validation.json` when using `--feedback-json`.
- `approve_listen.py` picks rewrite model at startup and passes it to `listen(rewrite_model=...)`.
- Removed separate `write_serverless_llama70b.py`, `write_serverless_qwen397b.py`, `approve_listen_llama70b.py`, `approve_listen_qwen397b.py`.
- `approve.py` accepts optional `rewrite_model` for subprocess rewrites.

Why:
- One writer entry point instead of parallel scripts per model; approval still uses matching model on feedback.

Files touched:
- `write_serverless.py` (now under `src/peachtree_blog/write/`)
- `approve_listen.py`, `approve.py`
- `write_common.py` (235B tput pricing)
- `CHANGELOG.md`

Tested:
- Import smoke test for `SERVERLESS_MODEL_CHOICES`

## 2026-06-04 - search_all_roofing 50-credit cap and write_serverless import fix

Changed:
- `search_all_roofing.py` defaults to 50 Tavily credits max (`--max-credits`); trims query plan and stops at runtime cap.
- Fixed missing `run_with_progress` import in `write_common.py` (from `cli_progress`).

Why:
- Lower weekly search spend than ~80 credits; unblock draft generation after `NameError`.

Files touched:
- `search_all_roofing.py`
- `write_common.py`
- `CHANGELOG.md`

Tested:
- Verified plan trim: 8 queries → 5 queries for 50-credit budget

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

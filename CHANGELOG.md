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

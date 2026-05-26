# Peachtree Restorations Blog Automation

This project is an automated blog-post pipeline for Peachtree Restorations. Its goal is to find timely Metro Atlanta roofing, storm, insurance, building-code, HOA, and exterior-repair news, turn the best sources into a GEO-optimized blog draft, send the draft for approval, and eventually publish approved posts to the company website.

The finished pipeline is intended to run every Monday morning through GitHub Actions. It will search for relevant local news, evaluate whether each source is useful, generate a draft in Peachtree's editorial style, email the draft for review, and publish only after approval.

Current build status: the project scaffold exists, the Tavily web search module is in progress, and the later evaluation, writing, approval, and posting modules are still placeholders.

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
3. Runs staged searches: 7-day priority sources, 30-day priority sources, 14-day broader news, then official sources if needed.
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
15. Saves the final result list to `output/drafts/search_results.json`.

Run it with:

```bash
conda run -n blog-automation python search.py
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

### Search Cost

Tavily does not bill search by LLM tokens. It uses API credits.

The current module uses `search_depth="advanced"`. Tavily's current docs state that:

- `basic` search costs 1 API credit per request.
- `advanced` search costs 2 API credits per request.

The current module has 19 strategy queries. Because each query uses advanced search, each full search stage costs about:

```text
19 queries * 2 credits = 38 Tavily API credits
```

The module stops once it finds enough quality candidates, so quiet weeks cost more than active weeks because fallback stages run. The maximum current run is four stages:

```text
38 credits/stage * 4 stages = 152 Tavily API credits
```

If the maximum path ran once per week, the search stage would use about:

```text
152 credits/week * 4 weeks = 608 credits/month
```

Tavily currently offers 1,000 free API credits per month on its free Researcher plan, so this search stage should fit comfortably inside the free tier during normal weekly usage.

Sources:

- Tavily Search API docs: https://docs.tavily.com/documentation/api-reference/endpoint/search
- Tavily credits and pricing docs: https://docs.tavily.com/documentation/api-credits

### Current Search Behavior

The current filter is intentionally strict. If Tavily finds Atlanta stories that are unrelated to roofing, storms, insurance, building safety, or exterior repair, those stories are filtered out before they reach the next pipeline stage.

At the moment, the search stage favors precision over raw volume. A quiet local news week may produce only a few source candidates. That is acceptable because the evaluation stage should receive fewer, cleaner candidates rather than many unrelated articles.

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

1. Reads candidates from `output/drafts/search_results.json`.
2. Loads the evaluation prompt from `prompts/evaluate.txt`.
3. Sends each source to Together AI for scoring.
4. Scores five dimensions: local relevance, roofing relevance, recency, source authority, and actionability.
5. Preserves the strategy metadata from search, including `strategy_cluster`, `pillar_topic`, and `trigger_window_hours`.
6. Adds a `recommended_angle` for the future blog-writing stage.
7. Writes all scored sources to `output/drafts/evaluated_sources.json`.
8. Writes sources with `weighted_score >= 6.0` to `output/drafts/kept_sources.json`.

Run live evaluation with:

```bash
conda run -n blog-automation python evaluate.py
```

Run a no-credit local test with:

```bash
conda run -n blog-automation python evaluate.py --mock
```

Mock mode is only for testing file flow and obvious filtering. The live Together evaluation should be stricter and more context-aware.

## Blog Writing

The third stage of the pipeline lives in `write.py`. This module turns evaluated source candidates into a Markdown blog draft.

### API Used

The writing stage uses Together AI through the `together` Python package.

The default writing model is:

```text
Qwen/Qwen2.5-72B-Instruct-Turbo
```

You can override that model in `.env`:

```env
TOGETHER_WRITING_MODEL=Qwen/Qwen2.5-72B-Instruct-Turbo
```

### How Writing Works

`write.py` currently:

1. Reads kept sources from `output/drafts/kept_sources.json`.
2. Loads the blog-writing prompt from `prompts/blog.txt`.
3. Loads editor feedback from `feedback/style_notes.txt`.
4. Formats source excerpts, evaluation reasons, strategy clusters, and recommended angles into a source block.
5. Calls Together AI to generate a Markdown draft.
6. Saves the draft to `output/drafts/YYYY-MM-DD-title-slug.md`.
7. Saves a validation report to `output/drafts/YYYY-MM-DD-title-slug-validation.json`.

Run live writing with:

```bash
conda run -n blog-automation python write.py
```

Run a no-credit local test with:

```bash
conda run -n blog-automation python write.py --mock
```

### Draft Validation

After generation, `write.py` checks the draft for core GEO requirements:

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

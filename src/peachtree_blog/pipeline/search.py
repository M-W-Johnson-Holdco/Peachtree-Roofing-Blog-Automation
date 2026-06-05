"""
Broad Metro Atlanta roofing search — keyword match only, 7-day recency gate.

No scoring penalties (sports, politics, duplicate topic, min score). Keeps sources
that match LOCAL_TERMS + TOPIC_TERMS/CLUSTER_TERMS from the Peachtree GEO strategy.
Only hard reject besides relevance: older than 7 days (configurable).

Run:
    python -m peachtree_blog.pipeline.search

Output:
    output/sources/search_results.json

Required environment:
    TAVILY_API_KEY
"""

from __future__ import annotations

import peachtree_blog._pycache_prefix  # noqa: F401

from peachtree_blog.paths import PROJECT_ROOT

import json
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from peachtree_blog.used_sources import normalize_source_url, used_source_urls


DEFAULT_MAX_AGE_DAYS = 7
DEFAULT_MAX_RESULTS_PER_QUERY = 6
DEFAULT_TARGET_RESULTS = 15
DEFAULT_QUERIES_PER_CLUSTER = 2
DEFAULT_MAX_TAVILY_CREDITS = 50
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "output" / "sources" / "search_results.json"
TAVILY_ADVANCED_SEARCH_CREDITS = 2

PRIORITY_SOURCES = [
    "fox5atlanta.com",
    "wsbtv.com",
    "ajc.com",
    "11alive.com",
    "weather.gov",
    "legis.ga.gov",
    "dca.ga.gov",
    "wsbradio.com",
    "wxia.com",
    "wgcl.com",
    "atlanta.curbed.com",
    "patch.com",
    "atlantabusinesschronicle.com",
]

SECONDARY_SOURCES = [
    "cbs46.com",
    "atlantan.com",
    "mdjonline.com",
    "gwinnettdailypost.com",
    "rockdalenewtoncitizen.com",
    "accesswdun.com",
    "reporternewspapers.net",
    "northside-neighbor.com",
    "neighbornewspapers.com",
    "cherokeetribune.com",
    "henryherald.com",
    "claytoncrescent.com",
    "newnan-times-herald.com",
    "douglascountysentinel.com",
    "payson roundup.com",
    "forsythnews.com",
    "alpharettatn.com",
    "roswellmagazine.com",
    "mariettadailyjournal.com",
    "smyrnaobserver.com",
    "tuscaloosanews.com",
]

OFFICIAL_SOURCES = [
    "weather.gov",
    "legis.ga.gov",
    "dca.ga.gov",
    "oci.georgia.gov",
    "atlantaga.gov",
    "fultoncountyga.gov",
    "dekalbcountyga.gov",
    "cobbcounty.org",
    "gwinnettcounty.com",
    "cherokeega.com",
    "fema.gov",
    "henrycountyga.gov",
    "claytoncountyga.gov",
    "douglascountyga.gov",
    "paulding.gov",
    "forsythco.com",
    "nws.noaa.gov",
    "spc.noaa.gov",
    "ready.gov",
    "insurance.georgia.gov",
    "dol.georgia.gov",
    "georgiabuilds.com",
    "icc-es.org",
]

EXCLUDED_DOMAINS = [
    "espn.com",
    "sports.yahoo.com",
    "cbssports.com",
    "si.com",
    "theathletic.com",
    "247sports.com",
    "on3.com",
    "bleacherreport.com",
    "mlb.com",
    "nba.com",
    "nfl.com",
    "pgatour.com",
    "golf.com",
    "foxsports.com",
    "nbcsports.com",
    "usatoday.com/sports",
    "people.com",
    "tmz.com",
    "eonline.com",
    "rollingstone.com",
]

STRATEGY_CLUSTERS = {
    "storm_damage": {
        "pillar_topic": "Metro Atlanta storm damage inspection and repair",
        "trigger_window_hours": 72,
        "queries": [
            "Metro Atlanta roof storm damage inspection homeowners",
            "Atlanta hail wind roof damage insurance claim homeowners",
            "NWS Atlanta severe thunderstorm hail wind damage Georgia roof",
            "Fulton DeKalb Cobb Gwinnett storm damage roof repair homeowners",
            "North Georgia severe weather roof damage homeowners Atlanta metro",
            "Atlanta metro tree fall roof damage storm homeowners",
            "Atlanta tornado warning roof damage homeowners",
            "Georgia hail size roof shingle damage homeowners repair",
            "Metro Atlanta flash flood roof water intrusion homeowners",
            "Atlanta derecho straight line wind roof damage homeowners",
            "Georgia severe weather roof inspection checklist homeowners",
            "Cobb Gwinnett Cherokee hail storm roof replacement homeowners",
            "Atlanta metro microburst roof structural damage homeowners",
        ],
    },
    "ga_insurance_navigation": {
        "pillar_topic": "Georgia roof insurance claims, RCV vs ACV, HB511",
        "trigger_window_hours": 48,
        "queries": [
            "Georgia roof insurance law homeowners claim deductible",
            "Georgia homeowners insurance roof replacement ACV RCV",
            "Georgia HB511 homeowners storm deductible insurance",
            "Atlanta roof insurance claim policy change homeowners",
            "Georgia insurance commissioner roof claim homeowners",
            "Metro Atlanta homeowners insurance rate roof age Georgia",
            "Georgia roof depreciation schedule insurance claim homeowners",
            "Georgia homeowners insurance nonrenewal roof age policy",
            "Georgia actual cash value roof claim homeowners dispute",
            "Metro Atlanta insurance adjuster roof inspection homeowners",
            "Georgia roof insurance deductible percentage homeowners storm",
            "Georgia homeowners insurance roof exclusion endorsement",
            "Atlanta roof insurance supplement claim underpaid homeowners",
            "Georgia catastrophe savings account HB511 homeowners deductible",
        ],
    },
    "roof_safety": {
        "pillar_topic": "Atlanta roof safety, fires, penetrations, structural risk",
        "trigger_window_hours": 48,
        "queries": [
            "Atlanta house fire roof damage HVAC roof penetration",
            "Metro Atlanta roof safety fire damage homeowners",
            "Atlanta construction safety roof structural inspection homeowners",
            "DeKalb Gwinnett Cobb fire roof damage homeowners",
            "Atlanta attic ventilation roof fire safety homeowners",
            "Atlanta building code roof inspection unsafe structure homeowners",
            "Metro Atlanta chimney roof fire damage homeowners",
            "Atlanta roof collapse structural failure homeowners inspection",
            "Georgia roof fire HVAC electrical conduit homeowners safety",
            "Atlanta attic mold moisture roof ventilation homeowners",
            "Metro Atlanta pipe boot flashing failure water intrusion homeowners",
            "Atlanta unsafe structure notice roof homeowners county",
            "Georgia roof ice dam freeze damage homeowners winter",
            "Atlanta solar panel roof penetration water damage homeowners",
            "Metro Atlanta flat roof ponding water structural risk homeowners",
        ],
    },
    "county_guides": {
        "pillar_topic": "County-specific roof guidance for Metro Atlanta",
        "trigger_window_hours": None,
        "queries": [
            "Fulton County roof permits storm damage homeowners",
            "DeKalb County roof repair storm damage homeowners",
            "Cobb County roof replacement insurance homeowners",
            "Gwinnett County roof damage hail wind homeowners",
            "Cherokee County roof repair storm damage homeowners",
            "Clayton County Georgia roof storm damage homeowners",
            "Henry County roof hail wind damage homeowners",
            "Fulton County building permit roof replacement residential",
            "DeKalb County unsafe structure notice roof homeowners",
            "Gwinnett County hail damage roof insurance claim homeowners",
            "Cobb County roof permit requirements residential homeowners",
            "Cherokee County storm damage roof inspection homeowners",
            "Douglas County Georgia roof repair permit storm homeowners",
            "Forsyth County roof replacement hail damage homeowners",
            "Paulding County storm roof damage homeowners repair",
            "Henry County homeowners insurance roof claim storm damage",
        ],
    },
}

LOCAL_TERMS = [
    "atlanta",
    "metro atlanta",
    "north georgia",
    "georgia",
    "fulton",
    "dekalb",
    "cobb",
    "gwinnett",
    "clayton",
    "cherokee",
    "henry",
    "henry county",
    "buckhead",
    "marietta",
    "alpharetta",
    "dunwoody",
    "woodstock",
    "east cobb",
    "vinings",
    "chamblee",
    "sandy springs",
    "roswell",
    "decatur",
    "lawrenceville",
    "smyrna",
    "paulding",
    "forsyth",
    "bartow",
    "newton",
    "rockdale",
    "fayette",
    "fayetteville",
    "peachtree city",
    "stockbridge",
    "mcdonough",
    "canton",
    "ball ground",
    "holly springs",
    "milton",
    "johns creek",
    "norcross",
    "buford",
    "suwanee",
    "duluth",
    "kennesaw",
    "acworth",
    "powder springs",
    "douglasville",
    "lithia springs",
    "college park",
    "east point",
    "hapeville",
    "forest park",
    "jonesboro",
]

TOPIC_TERMS = [
    "roof",
    "roofing",
    "shingle",
    "gutter",
    "siding",
    "exterior",
    "storm",
    "hail",
    "wind",
    "thunderstorm",
    "tornado",
    "weather",
    "insurance",
    "claim",
    "building code",
    "hoa",
    "fire",
    "damage",
    "flooding",
    "permit",
    "inspection",
    "unsafe",
    "safety",
    "structural",
    "construction",
    "hvac",
    "pipe boot",
    "flashing",
    "attic",
    "ventilation",
    "deductible",
    "rcv",
    "acv",
    "hb511",
    "house bill 511",
    "architectural shingle",
    "asphalt shingle",
    "metal roof",
    "flat roof",
    "tpo",
    "epdm",
    "modified bitumen",
    "slate roof",
    "tile roof",
    "ridge cap",
    "ridge vent",
    "soffit",
    "fascia",
    "drip edge",
    "ice barrier",
    "underlayment",
    "felt paper",
    "synthetic underlayment",
    "decking",
    "roof deck",
    "plywood decking",
    "osb decking",
    "roof truss",
    "rafter",
    "skylight",
    "chimney flashing",
    "step flashing",
    "valley flashing",
    "pipe collar",
    "boot seal",
    "roof cement",
    "caulk",
    "sealant",
    "granule loss",
    "granule",
    "blistering",
    "curling shingle",
    "lifted shingle",
    "cracked shingle",
    "missing shingle",
    "moss",
    "algae",
    "staining",
    "ponding water",
    "ice dam",
    "gutter guard",
    "downspout",
    "soffit vent",
    "ridge ventilation",
    "power attic ventilator",
    "solar attic fan",
    "roofing contractor",
    "licensed roofer",
    "roofing estimate",
    "roofing warranty",
    "manufacturer warranty",
    "workmanship warranty",
    "gaf",
    "owens corning",
    "certainteed",
    "tamko",
    "atlas roofing",
    "iko",
    "emergency tarp",
    "temporary repair",
    "supplemental claim",
    "public adjuster",
    "xactimate",
    "replacement cost",
    "actual cash value",
    "depreciation",
    "recoverable depreciation",
    "non recoverable depreciation",
    "roof age",
    "roof lifespan",
    "roof inspection report",
    "drone inspection",
]

CLUSTER_TERMS = {
    "storm_damage": [
        "roof",
        "storm",
        "hail",
        "wind",
        "thunderstorm",
        "tornado",
        "weather",
        "insurance",
        "claim",
        "missing shingle",
        "lifted shingle",
        "granule loss",
        "tree branch",
        "emergency tarp",
        "temporary repair",
        "roof leak",
        "water intrusion",
        "ice dam",
        "ponding water",
        "derecho",
        "microburst",
        "straight line wind",
    ],
    "ga_insurance_navigation": [
        "roof",
        "insurance",
        "claim",
        "deductible",
        "rcv",
        "acv",
        "hb511",
        "house bill 511",
        "policy",
        "replacement cost",
        "actual cash value",
        "depreciation",
        "recoverable depreciation",
        "supplemental claim",
        "public adjuster",
        "xactimate",
        "roof age",
        "nonrenewal",
        "endorsement",
        "exclusion",
        "catastrophe savings account",
        "underpaid claim",
    ],
    "roof_safety": [
        "roof",
        "fire",
        "safety",
        "structural",
        "construction",
        "inspection",
        "hvac",
        "attic",
        "ventilation",
        "flashing",
        "pipe boot",
        "boot seal",
        "chimney flashing",
        "step flashing",
        "granule loss",
        "moss",
        "algae",
        "mold",
        "moisture",
        "rot",
        "roof collapse",
        "structural failure",
        "solar panel",
        "flat roof",
        "ponding water",
        "ice dam",
        "power attic ventilator",
    ],
    "county_guides": [
        "roof",
        "permit",
        "storm",
        "hail",
        "wind",
        "insurance",
        "replacement",
        "repair",
        "building permit",
        "residential permit",
        "permit requirements",
        "unsafe structure",
        "code violation",
        "hoa requirement",
        "county ordinance",
        "inspection required",
        "licensed contractor required",
    ],
}

SEARCH_PLAN = [
    {
        "query": query,
        "strategy_cluster": cluster_name,
        "pillar_topic": cluster["pillar_topic"],
        "trigger_window_hours": cluster["trigger_window_hours"],
    }
    for cluster_name, cluster in STRATEGY_CLUSTERS.items()
    for query in cluster["queries"]
]

SEARCH_STAGES = [
    {
        "name": "priority_7_day_news",
        "days": 7,
        "topic": "news",
        "search_depth": "advanced",
        "include_domains": PRIORITY_SOURCES,
        "exclude_domains": None,
        "max_results_per_query": 6,
    },
    {
        "name": "priority_30_day_news",
        "days": 30,
        "topic": "news",
        "search_depth": "advanced",
        "include_domains": PRIORITY_SOURCES,
        "exclude_domains": None,
        "max_results_per_query": 6,
    },
    {
        "name": "secondary_14_day_news",
        "days": 14,
        "topic": "news",
        "search_depth": "advanced",
        "include_domains": SECONDARY_SOURCES,
        "exclude_domains": None,
        "max_results_per_query": 6,
    },
    {
        "name": "broad_14_day_news",
        "days": 14,
        "topic": "news",
        "search_depth": "advanced",
        "include_domains": None,
        "exclude_domains": EXCLUDED_DOMAINS,
        "max_results_per_query": 6,
    },
    {
        "name": "official_30_day_general",
        "days": 30,
        "topic": "general",
        "search_depth": "advanced",
        "include_domains": OFFICIAL_SOURCES,
        "exclude_domains": None,
        "max_results_per_query": 6,
    },
]


LOG_PREFIX = "search"


def _load_client():
    try:
        from tavily import TavilyClient
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: tavily-python. Install with "
            "`python -m pip install -r requirements.txt`."
        ) from exc

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "TAVILY_API_KEY is not set. Copy .env.template to .env and add your Tavily key."
        )
    return TavilyClient(api_key=api_key)


def _source_domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _domain_matches_list(domain: str, sources: list[str]) -> bool:
    return any(domain == source or domain.endswith(f".{source}") for source in sources)


def _is_priority_source(url: str) -> bool:
    return _domain_matches_list(_source_domain(url), PRIORITY_SOURCES)


def _is_secondary_source(url: str) -> bool:
    domain = _source_domain(url)
    return _domain_matches_list(domain, SECONDARY_SOURCES) and not _domain_matches_list(
        domain, PRIORITY_SOURCES
    )


def _is_official_source(url: str) -> bool:
    return _domain_matches_list(_source_domain(url), OFFICIAL_SOURCES)


def estimate_tavily_credits(query_count: int, stage_count: int) -> int:
    return query_count * stage_count * TAVILY_ADVANCED_SEARCH_CREDITS


def cap_search_plan_for_credits(
    plan: list[dict],
    *,
    max_credits: int,
    stage_count: int,
) -> list[dict]:
    """Limit active queries so a full multi-stage run stays within the credit budget."""
    if max_credits <= 0 or not plan or stage_count <= 0:
        return plan

    max_api_calls = max_credits // TAVILY_ADVANCED_SEARCH_CREDITS
    max_queries = max(1, max_api_calls // stage_count)
    if len(plan) <= max_queries:
        return plan
    return plan[:max_queries]


def build_active_search_plan(
    *,
    queries_per_cluster: int = DEFAULT_QUERIES_PER_CLUSTER,
    use_all_queries: bool = False,
    rotation_week: int | None = None,
) -> list[dict]:
    if use_all_queries or queries_per_cluster <= 0:
        return list(SEARCH_PLAN)

    week_number = rotation_week or datetime.now(timezone.utc).isocalendar().week
    plan: list[dict] = []
    for cluster_name, cluster in STRATEGY_CLUSTERS.items():
        queries = cluster["queries"]
        if not queries:
            continue
        count = min(queries_per_cluster, len(queries))
        start_index = (week_number - 1) % len(queries)
        for offset in range(count):
            query = queries[(start_index + offset) % len(queries)]
            plan.append(
                {
                    "query": query,
                    "strategy_cluster": cluster_name,
                    "pillar_topic": cluster["pillar_topic"],
                    "trigger_window_hours": cluster["trigger_window_hours"],
                }
            )
    return plan


def _term_matches(text: str, term: str) -> bool:
    normalized = term.lower()
    if " " in normalized:
        return normalized in text
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", text))


def _matched_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if _term_matches(text, term)]


def _parse_published_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _effective_published_date(result: dict) -> datetime | None:
    parsed = _parse_published_date(result.get("published_date", ""))
    if parsed:
        return parsed

    combined = f"{result.get('title', '')} {result.get('url', '')}".lower()

    compact = re.search(r"(?:/|_|-)(20\d{2})(\d{2})(\d{2})(?:[_/.-]|$)", combined)
    if compact:
        try:
            return datetime(
                int(compact.group(1)),
                int(compact.group(2)),
                int(compact.group(3)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            pass

    dashed = re.search(r"(?:/|_|-)(20\d{2})-(\d{2})-(\d{2})(?:[_/.-]|$)", combined)
    if dashed:
        try:
            return datetime(
                int(dashed.group(1)),
                int(dashed.group(2)),
                int(dashed.group(3)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            pass

    years = [int(year) for year in re.findall(r"\b(20\d{2})\b", combined)]
    if years:
        year = max(years)
        if year < datetime.now(timezone.utc).year:
            return datetime(year, 12, 31, tzinfo=timezone.utc)

    return None


def _content_age_days(result: dict) -> int | None:
    parsed = _effective_published_date(result)
    if not parsed:
        return None
    return (datetime.now(timezone.utc) - parsed).days


def _is_within_recency_window(result: dict, max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> bool:
    age_days = _content_age_days(result)
    if age_days is None:
        if result.get("search_stage") in {"broad_14_day_news", "official_30_day_general"}:
            return False
        return True
    return age_days <= max_age_days


def _article_evidence(result: dict) -> dict[str, str]:
    title_url = " ".join([result.get("title", ""), result.get("url", "")]).lower()
    early_content = " ".join(
        [
            result.get("title", ""),
            result.get("url", ""),
            result.get("content", "")[:1400],
        ]
    ).lower()
    return {"title_url": title_url, "early_content": early_content}


def _normalize_result(item: dict, search_item: dict, stage: dict) -> dict:
    url = item.get("url", "").strip()
    return {
        "title": item.get("title", "").strip(),
        "url": url,
        "domain": _source_domain(url),
        "content": item.get("content", "").strip(),
        "published_date": item.get("published_date") or item.get("publishedDate") or "",
        "tavily_score": item.get("score", 0.0),
        "priority_source": _is_priority_source(url),
        "secondary_source": _is_secondary_source(url),
        "official_source": _is_official_source(url),
        "query": search_item["query"],
        "strategy_cluster": search_item["strategy_cluster"],
        "pillar_topic": search_item["pillar_topic"],
        "trigger_window_hours": search_item["trigger_window_hours"],
        "search_stage": stage["name"],
        "search_days": stage["days"],
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def _collect_matched_terms(result: dict) -> dict[str, object]:
    evidence = _article_evidence(result)
    text = f"{evidence['title_url']} {evidence['early_content']}"
    cluster = result.get("strategy_cluster", "")
    cluster_terms = CLUSTER_TERMS.get(cluster, TOPIC_TERMS)

    local_terms = sorted(set(_matched_terms(text, LOCAL_TERMS)))
    topic_terms = sorted(set(_matched_terms(text, TOPIC_TERMS)))
    cluster_matched = sorted(set(_matched_terms(text, cluster_terms)))

    return {
        "local_terms": local_terms,
        "topic_terms": topic_terms,
        "cluster_terms": cluster_matched,
        "scoring_mode": "roofing_keyword_match_only",
    }


def _relevance_failure_reason(result: dict, matched: dict[str, object], max_age_days: int) -> str | None:
    if not _is_within_recency_window(result, max_age_days):
        return "outside_recency_window"
    if not matched["local_terms"]:
        return "missing_local_terms"
    if not matched["topic_terms"] and not matched["cluster_terms"]:
        return "missing_roofing_topic"
    return None


def _match_score(matched: dict[str, object]) -> float:
    return float(len(matched["local_terms"]) + len(matched["topic_terms"]) + len(matched["cluster_terms"]))


def _ingest_tavily_items(
    raw_items: list[dict],
    *,
    search_item: dict,
    stage: dict,
    results_by_url: dict[str, dict],
    blocked_urls: set[str],
    max_age_days: int,
) -> tuple[int, dict[str, int]]:
    skipped_used = 0
    pipeline_rejects: dict[str, int] = {}

    for item in raw_items:
        url = str(item.get("url", "")).strip()
        if not url:
            continue

        if blocked_urls and normalize_source_url(url) in blocked_urls:
            skipped_used += 1
            continue

        result = _normalize_result(item, search_item, stage)
        matched = _collect_matched_terms(result)
        result["matched_terms"] = matched
        result["search_quality_score"] = _match_score(matched)
        result["content_age_days"] = _content_age_days(result)
        result["scoring_mode"] = matched["scoring_mode"]

        failure = _relevance_failure_reason(result, matched, max_age_days)
        if failure:
            pipeline_rejects[failure] = pipeline_rejects.get(failure, 0) + 1
            continue

        existing = results_by_url.get(url)
        if not existing or result["search_quality_score"] > existing["search_quality_score"]:
            results_by_url[url] = result

    return skipped_used, pipeline_rejects


def _sort_results(results: list[dict]) -> list[dict]:
    return sorted(
        results,
        key=lambda result: (
            result.get("content_age_days") is not None,
            -(result.get("content_age_days") or 9999),
            result["search_quality_score"],
            result["priority_source"],
            result.get("secondary_source", False),
            result["tavily_score"],
        ),
        reverse=True,
    )


def search_roofing_news(
    max_results_per_query: int = DEFAULT_MAX_RESULTS_PER_QUERY,
    target_results: int | None = DEFAULT_TARGET_RESULTS,
    *,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    max_tavily_credits: int = DEFAULT_MAX_TAVILY_CREDITS,
    skip_used_sources: bool = True,
    queries_per_cluster: int = DEFAULT_QUERIES_PER_CLUSTER,
    use_all_queries: bool = False,
    rotation_week: int | None = None,
) -> list[dict]:
    load_dotenv(PROJECT_ROOT / ".env")
    client = _load_client()

    blocked_urls: set[str] = set()
    if skip_used_sources:
        blocked_urls = used_source_urls()
        if blocked_urls:
            print(f"[{LOG_PREFIX}] Skipping {len(blocked_urls)} previously used source URL(s)")

    active_plan = build_active_search_plan(
        queries_per_cluster=queries_per_cluster,
        use_all_queries=use_all_queries,
        rotation_week=rotation_week,
    )
    planned_query_count = len(active_plan)
    active_plan = cap_search_plan_for_credits(
        active_plan,
        max_credits=max_tavily_credits,
        stage_count=len(SEARCH_STAGES),
    )
    query_count = len(active_plan)
    planned_credits = estimate_tavily_credits(planned_query_count, len(SEARCH_STAGES))
    max_credits = min(planned_credits, max_tavily_credits)
    week_number = rotation_week or datetime.now(timezone.utc).isocalendar().week
    target_note = target_results if target_results is not None else "all"
    trim_note = ""
    if query_count < planned_query_count:
        trim_note = f", trimmed {planned_query_count}→{query_count} queries for {max_tavily_credits}-credit cap"
    print(
        f"[{LOG_PREFIX}] Plan: {query_count} active queries "
        f"({queries_per_cluster}/cluster, ISO week {week_number}) "
        f"from {len(SEARCH_PLAN)} total across {len(SEARCH_STAGES)} stages "
        f"(target {target_note}, max age {max_age_days}d, max ~{max_credits} credits{trim_note})"
    )

    results_by_url: dict[str, dict] = {}
    stages = [{**stage, "days": max_age_days, "max_results_per_query": max_results_per_query} for stage in SEARCH_STAGES]
    queries_run = 0
    skipped_used_sources = 0
    pipeline_rejects: dict[str, int] = {}
    credit_limit_reached = False

    for stage_index, stage in enumerate(stages):
        if credit_limit_reached:
            break
        print(f"[{LOG_PREFIX}] Running stage: {stage['name']}")
        is_last_stage = stage_index == len(stages) - 1

        for search_item in active_plan:
            credits_after_call = (queries_run + 1) * TAVILY_ADVANCED_SEARCH_CREDITS
            if credits_after_call > max_tavily_credits:
                print(
                    f"[{LOG_PREFIX}] Tavily credit cap ({max_tavily_credits}) reached — "
                    "stopping search"
                )
                credit_limit_reached = True
                break

            query = search_item["query"]
            try:
                response = client.search(
                    query=query,
                    search_depth=stage["search_depth"],
                    topic=stage["topic"],
                    days=stage["days"],
                    max_results=stage["max_results_per_query"],
                    include_domains=stage["include_domains"],
                    exclude_domains=stage["exclude_domains"],
                    include_raw_content=False,
                )
                queries_run += 1
            except Exception as exc:
                print(f"[{LOG_PREFIX}] Query failed for {query!r}: {exc}")
                continue

            skipped, stage_rejects = _ingest_tavily_items(
                response.get("results", []),
                search_item=search_item,
                stage=stage,
                results_by_url=results_by_url,
                blocked_urls=blocked_urls,
                max_age_days=max_age_days,
            )
            skipped_used_sources += skipped
            for reason, count in stage_rejects.items():
                pipeline_rejects[reason] = pipeline_rejects.get(reason, 0) + count

            if (
                target_results is not None
                and is_last_stage
                and len(results_by_url) >= target_results
            ):
                print(
                    f"[{LOG_PREFIX}] Target of {target_results} reached mid-stage — "
                    f"skipping remaining queries in {stage['name']}"
                )
                break

        print(f"[{LOG_PREFIX}] Stage {stage['name']} total kept so far: {len(results_by_url)}")

    results = _sort_results(list(results_by_url.values()))
    if target_results is not None:
        results = results[:target_results]

    credits_used = queries_run * TAVILY_ADVANCED_SEARCH_CREDITS
    skipped_note = f", skipped {skipped_used_sources} previously used" if skipped_used_sources else ""
    reject_note = ""
    if pipeline_rejects:
        reject_summary = ", ".join(
            f"{reason}={count}" for reason, count in sorted(pipeline_rejects.items())
        )
        reject_note = f"; rejects ({reject_summary})"

    domains = sorted({result["domain"] for result in results})
    print(
        f"[{LOG_PREFIX}] Found {len(results)} unique results "
        f"from {query_count} active queries "
        f"({queries_run} API calls, ~{credits_used} Tavily credits{skipped_note}{reject_note})"
    )
    print(f"[{LOG_PREFIX}] Domains ({len(domains)}): {', '.join(domains)}")

    return results


def _json_safe(value: object) -> object:
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def save_results(results: list[dict], path: str | Path = DEFAULT_OUTPUT_PATH) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(_json_safe(results), f, indent=2)
    print(f"[{LOG_PREFIX}] Results saved to {output_path}")
    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Broad Metro Atlanta roofing search — 7-day recency, keyword match only."
    )
    parser.add_argument(
        "--target-results",
        type=int,
        default=DEFAULT_TARGET_RESULTS,
        help=f"Max results to keep; use 0 for no cap (default: {DEFAULT_TARGET_RESULTS}).",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=DEFAULT_MAX_AGE_DAYS,
        help=f"Reject sources older than this many days (default: {DEFAULT_MAX_AGE_DAYS}).",
    )
    parser.add_argument(
        "--max-credits",
        type=int,
        default=DEFAULT_MAX_TAVILY_CREDITS,
        help=f"Stop after this many Tavily credits (default: {DEFAULT_MAX_TAVILY_CREDITS}).",
    )
    parser.add_argument("--max-results-per-query", type=int, default=DEFAULT_MAX_RESULTS_PER_QUERY)
    parser.add_argument("--include-used-sources", action="store_true")
    parser.add_argument("--queries-per-cluster", type=int, default=DEFAULT_QUERIES_PER_CLUSTER)
    parser.add_argument("--all-queries", action="store_true")
    parser.add_argument("--rotation-week", type=int)
    args = parser.parse_args()

    target = None if args.target_results == 0 else args.target_results

    print("=" * 60)
    print("Peachtree Blog Pipeline - search.py")
    print(
        f"Target {target or 'all'} results | keep within {args.max_age_days}d | "
        f"roofing + local keyword match | no score penalties"
    )
    print("=" * 60)

    try:
        results = search_roofing_news(
            max_results_per_query=args.max_results_per_query,
            target_results=target,
            max_age_days=args.max_age_days,
            max_tavily_credits=args.max_credits,
            skip_used_sources=not args.include_used_sources,
            queries_per_cluster=args.queries_per_cluster,
            use_all_queries=args.all_queries,
            rotation_week=args.rotation_week,
        )
    except (EnvironmentError, RuntimeError) as exc:
        print(f"\n[{LOG_PREFIX}] Setup needed: {exc}")
        raise SystemExit(1) from exc

    save_results(results)
    if not results:
        print("\n[!] No results kept. Try --include-used-sources or --all-queries.")
    else:
        print(f"\n[{LOG_PREFIX}] Done — {len(results)} results saved")

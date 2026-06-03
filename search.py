import json
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from used_sources import normalize_source_url, used_source_urls

"""
Tavily news search for Peachtree's GEO content strategy.

Run directly with:
    python search.py

Required environment:
    TAVILY_API_KEY
"""

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DAYS_BACK = 7
DEFAULT_MAX_RESULTS_PER_QUERY = 5
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "output" / "sources" / "search_results.json"
DEFAULT_TARGET_RESULTS = 10
DEFAULT_QUERIES_PER_CLUSTER = 2
RECENT_TOPIC_LOOKBACK_DAYS = 30
TAVILY_ADVANCED_SEARCH_CREDITS = 2

# Results from these outlets should receive a source-authority bonus in evaluate.py.
PRIORITY_SOURCES = [
    "fox5atlanta.com",
    "wsbtv.com",
    "ajc.com",
    "11alive.com",
    "weather.gov",
    "legis.ga.gov",
    "dca.ga.gov",
]

# Regional Metro Atlanta outlets searched in a dedicated secondary stage.
SECONDARY_SOURCES = [
    "cbs46.com",
    "atlantan.com",
    "mdjonline.com",
    "gwinnettdailypost.com",
    "rockdalenewtoncitizen.com",
    "accesswdun.com",
    "reporternewspapers.net",
    "northside-neighbor.com",
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
]

EXCLUDED_DOMAINS = [
    "espn.com",
    "sports.yahoo.com",
    "cbssports.com",
    "si.com",
    "theathletic.com",
    "247sports.com",
    "on3.com",
]

# From Peachtree_GEO_Content_Strategy_2026: every post should deepen one of
# these territories or react to a breaking local event that connects to them.
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
]

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
        "max_results_per_query": 5,
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
        "max_results_per_query": 5,
    },
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
    ],
}

TERRITORY_SIGNAL_TERMS = {
    "storm_damage": [
        "storm",
        "hail",
        "wind",
        "thunderstorm",
        "tornado",
        "weather",
        "tree",
        "damage",
        "inspection",
    ],
    "ga_insurance_navigation": [
        "insurance",
        "claim",
        "deductible",
        "policy",
        "premium",
        "rcv",
        "acv",
        "hb511",
        "house bill 511",
    ],
    "roof_safety": [
        "fire",
        "safety",
        "unsafe",
        "structural",
        "inspection",
        "hvac",
        "attic",
        "ventilation",
        "construction",
    ],
    "county_guides": [
        "fulton",
        "dekalb",
        "cobb",
        "gwinnett",
        "cherokee",
        "county",
        "permit",
        "hoa",
    ],
}

SEMANTIC_RELEVANCE_RULES = {
    "direct_roofing": [
        ["roof", "roofing", "shingle", "flashing", "gutter", "siding", "exterior"],
        ["repair", "replace", "replacement", "inspection", "damage", "leak", "claim", "permit"],
    ],
    "storm_property_risk": [
        ["storm", "hail", "wind", "thunderstorm", "tornado", "tree", "weather"],
        ["home", "house", "property", "roof", "damage", "inspection", "insurance"],
    ],
    "insurance_roof_claim": [
        ["insurance", "claim", "deductible", "policy", "premium", "rcv", "acv", "hb511", "house bill 511"],
        ["home", "homeowner", "roof", "storm", "property", "replacement", "repair"],
    ],
    "safety_structure": [
        ["fire", "unsafe", "safety", "structural", "inspection", "construction", "hvac"],
        ["roof", "attic", "building", "home", "house", "structure", "ventilation"],
    ],
    "county_homeowner_guidance": [
        ["fulton", "dekalb", "cobb", "gwinnett", "cherokee", "county"],
        ["roof", "permit", "storm", "insurance", "repair", "replacement", "inspection"],
    ],
}

OFF_TOPIC_PENALTY_TERMS = {
    "sports": {
        "penalty": 7,
        "terms": [
            "sports",
            "fantasy",
            "football",
            "basketball",
            "baseball",
            "soccer",
            "panthers",
            "falcons",
            "braves",
            "hawks",
            "atlanta united",
            "quarterback",
            "recruiting",
            "draft pick",
            "locked-on",
            "locked on",
        ],
    },
    "politics": {
        "penalty": 5,
        "terms": [
            "election",
            "campaign",
            "commissioner race",
            "runoff",
            "candidate",
            "poll",
            "vote",
            "primary",
        ],
    },
    "generic_or_unrelated_insurance": {
        "penalty": 5,
        "terms": [
            "car insurance",
            "auto insurance",
            "liability policy",
            "general liability",
            "health insurance",
            "life insurance",
        ],
    },
    "crime_or_accident": {
        "penalty": 4,
        "terms": [
            "shooting",
            "shot in downtown",
            "injured biker",
            "crash",
            "arrested",
            "murder",
            "cruise fight",
        ],
    },
    "generic_local_news": {
        "penalty": 2,
        "terms": [
            "restaurant",
            "concert",
            "festival",
            "traffic",
            "school board",
            "celebrity",
        ],
    },
}

DISQUALIFYING_TERMS = [
    "sports",
    "fantasy",
    "football",
    "basketball",
    "baseball",
    "soccer",
    "panthers",
    "falcons",
    "braves",
    "hawks",
    "atlanta united",
    "ota",
    "quarterback",
    "recruiting",
    "draft pick",
    "locked-on",
    "locked on",
    "car insurance",
    "auto insurance",
    "liability policy",
    "general liability",
    "injured biker",
    "commissioner race",
    "runoff",
    "cruise fight",
    "shot in downtown",
    "shooting",
]

DEFAULT_MIN_QUALITY_SCORE = 7.5

HOMEOWNER_HEADLINE_TERMS = [
    "homeowner",
    "homeowners",
    "your roof",
    "your home",
    "inspect",
    "inspection",
    "replace",
    "repair",
    "damage",
    "insurance claim",
    "deductible",
    "what to do",
    "should you",
    "how to",
    "warning",
    "alert",
    "risk",
    "protect",
]

ACTIONABILITY_TERMS = [
    "what to do",
    "how to",
    "steps to",
    "should you",
    "checklist",
    "inspect",
    "call",
    "contact",
    "schedule",
    "before",
    "after",
    "warning",
    "alert",
    "required",
    "deadline",
    "expires",
    "act now",
    "immediately",
    "urgent",
    "time sensitive",
]

SEASONAL_WEIGHTS = {
    1: 0.5,
    2: 0.5,
    3: 0.8,
    4: 1.2,
    5: 1.5,
    6: 1.5,
    7: 1.3,
    8: 1.3,
    9: 1.2,
    10: 0.8,
    11: 0.5,
    12: 0.5,
}


def _load_client():
    """Import Tavily only when a real search is requested."""
    try:
        from tavily import TavilyClient
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: tavily-python. Install dependencies with "
            "`python -m pip install -r requirements.txt`."
        ) from exc

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "TAVILY_API_KEY is not set. Copy .env.template to .env and add your Tavily key."
        )

    return TavilyClient(api_key=api_key)


def _source_domain(url: str) -> str:
    domain = urlparse(url).netloc.lower()
    return domain.removeprefix("www.")


def _domain_matches_list(domain: str, sources: list[str]) -> bool:
    return any(domain == source or domain.endswith(f".{source}") for source in sources)


def _is_priority_source(url: str) -> bool:
    return _domain_matches_list(_source_domain(url), PRIORITY_SOURCES)


def _is_secondary_source(url: str) -> bool:
    domain = _source_domain(url)
    return _domain_matches_list(domain, SECONDARY_SOURCES) and not _domain_matches_list(domain, PRIORITY_SOURCES)


def _is_official_source(url: str) -> bool:
    return _domain_matches_list(_source_domain(url), OFFICIAL_SOURCES)


def estimate_tavily_credits(query_count: int, stage_count: int) -> int:
    """Estimate Tavily credits for advanced search (2 credits per query per stage)."""
    return query_count * stage_count * TAVILY_ADVANCED_SEARCH_CREDITS


def build_active_search_plan(
    *,
    queries_per_cluster: int = DEFAULT_QUERIES_PER_CLUSTER,
    use_all_queries: bool = False,
    rotation_week: int | None = None,
) -> list[dict]:
    """Select a rotating subset of strategy queries to limit Tavily API calls."""
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


def _tokenize_topic(text: str) -> set[str]:
    stopwords = {
        "about",
        "after",
        "and",
        "are",
        "before",
        "from",
        "how",
        "into",
        "that",
        "the",
        "this",
        "what",
        "when",
        "where",
        "with",
        "your",
    }
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    return {token for token in tokens if len(token) >= 4 and token not in stopwords}


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


def _recency_score(result: dict) -> float:
    parsed = _parse_published_date(result.get("published_date", ""))
    if not parsed:
        return 0.0

    age_days = (datetime.now(timezone.utc) - parsed).days
    if age_days <= 1:
        return 5.0
    if age_days <= 3:
        return 4.0
    if age_days <= 7:
        return 3.0
    if age_days <= 14:
        return 2.0
    if age_days <= 30:
        return 1.0
    return 0.0


def _headline_homeowner_score(result: dict) -> float:
    title = result.get("title", "").lower()
    matches = _matched_terms(title, HOMEOWNER_HEADLINE_TERMS)
    if len(matches) >= 3:
        return 3.0
    if len(matches) >= 2:
        return 2.0
    if len(matches) >= 1:
        return 1.0
    return 0.0


def _seasonal_bonus(result: dict) -> float:
    cluster = result.get("strategy_cluster", "")
    if cluster not in ("storm_damage", "roof_safety"):
        return 0.0
    weight = SEASONAL_WEIGHTS.get(datetime.now().month, 1.0)
    return round((weight - 1.0) * 3, 2)


def _content_depth_score(result: dict) -> float:
    word_count = len(str(result.get("content", "")).split())
    if word_count >= 300:
        return 2.0
    if word_count >= 150:
        return 1.0
    if word_count >= 50:
        return 0.5
    return 0.0


def _actionability_score(result: dict) -> float:
    evidence = _article_evidence(result)
    title_matches = _matched_terms(evidence["title_url"], ACTIONABILITY_TERMS)
    content_matches = _matched_terms(evidence["early_content"], ACTIONABILITY_TERMS)
    total = len(set(title_matches + content_matches))
    if total >= 3:
        return 2.0
    if total >= 1:
        return 1.0
    return 0.0


def _is_within_stage_window(result: dict) -> bool:
    parsed = _parse_published_date(result.get("published_date", ""))
    if not parsed:
        return False

    age_days = (datetime.now(timezone.utc) - parsed).days
    return age_days <= int(result.get("search_days") or DEFAULT_DAYS_BACK)


def _searchable_text(result: dict) -> str:
    searchable_text = " ".join(
        [
            result.get("title", ""),
            result.get("content", ""),
            result.get("url", ""),
            result.get("domain", ""),
        ]
    ).lower()
    return searchable_text


def _article_evidence(result: dict) -> dict[str, str]:
    title_url = " ".join([result.get("title", ""), result.get("url", "")]).lower()
    early_content = " ".join(
        [
            result.get("title", ""),
            result.get("url", ""),
            result.get("content", "")[:1400],
        ]
    ).lower()
    full_text = _searchable_text(result)
    return {
        "title_url": title_url,
        "early_content": early_content,
        "full_text": full_text,
    }


def _is_disqualified(result: dict) -> bool:
    penalty = result.get("off_topic_penalty")
    if penalty is None:
        penalty, _ = _off_topic_penalty(result)
    return penalty >= 7


def _territory_alignment(result: dict) -> dict:
    evidence = _article_evidence(result)
    title_url = evidence["title_url"]
    early_content = evidence["early_content"]
    matched_territories = {}

    for territory, terms in TERRITORY_SIGNAL_TERMS.items():
        title_matches = _matched_terms(title_url, terms)
        content_matches = _matched_terms(early_content, terms)
        matches = sorted(set(title_matches + content_matches))
        if matches:
            matched_territories[territory] = matches

    primary = result.get("strategy_cluster", "")
    primary_matches = matched_territories.get(primary, [])
    score = 0
    if primary_matches:
        score += 3
    if len(primary_matches) >= 3:
        score += 2
    secondary_count = max(0, len(matched_territories) - (1 if primary_matches else 0))
    score += min(secondary_count * 2, 4)

    return {
        "score": min(score, 9),
        "matched_territories": matched_territories,
        "multi_territory_bonus": min(secondary_count * 2, 4),
    }


def _semantic_relevance(result: dict) -> dict:
    evidence = _article_evidence(result)
    title_url = evidence["title_url"]
    early_content = evidence["early_content"]
    matched_rules = {}

    for rule_name, term_groups in SEMANTIC_RELEVANCE_RULES.items():
        group_matches = []
        for group in term_groups:
            matches = sorted(set(_matched_terms(early_content, group) + _matched_terms(title_url, group)))
            group_matches.append(matches)
        if all(group_matches):
            matched_rules[rule_name] = group_matches

    score = min(10, len(matched_rules) * 3)
    if _matched_terms(title_url, ["roof", "roofing", "storm", "insurance", "fire", "safety", "permit"]):
        score = min(10, score + 2)

    return {
        "score": score,
        "matched_rules": matched_rules,
        "passes": score >= 4,
    }


def _off_topic_penalty(result: dict) -> tuple[int, dict[str, list[str]]]:
    evidence = _article_evidence(result)
    matched_categories = {}
    total_penalty = 0

    for category, config in OFF_TOPIC_PENALTY_TERMS.items():
        title_matches = _matched_terms(evidence["title_url"], config["terms"])
        content_matches = _matched_terms(evidence["early_content"], config["terms"])
        matches = sorted(set(title_matches + content_matches))
        if not matches:
            continue

        # A title match is stronger evidence that the whole source is off-topic.
        penalty = int(config["penalty"]) + (2 if title_matches else 0)
        matched_categories[category] = matches
        total_penalty += penalty

    return min(total_penalty, 10), matched_categories


def _recent_draft_topics(lookback_days: int = RECENT_TOPIC_LOOKBACK_DAYS) -> list[dict]:
    draft_dir = PROJECT_ROOT / "output" / "drafts"
    md_dir = draft_dir / "drafts_md"
    search_dirs = [md_dir]
    if draft_dir.exists():
        search_dirs.append(draft_dir)

    now = datetime.now(timezone.utc)
    topics = []
    seen_paths: set[str] = set()
    for directory in search_dirs:
        if not directory.exists():
            continue
        for path in directory.glob("*.md"):
            key = str(path.resolve())
            if key in seen_paths:
                continue
            seen_paths.add(key)
            try:
                modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            except OSError:
                continue

            age_days = (now - modified_at).days
            if age_days > lookback_days:
                continue

            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            title = ""
            for line in text.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            topic_text = " ".join([title, path.stem])
            topics.append(
                {
                    "path": str(path.relative_to(PROJECT_ROOT)),
                    "title": title or path.stem,
                    "tokens": _tokenize_topic(topic_text),
                    "age_days": age_days,
                }
            )

    return topics


def _duplicate_topic_penalty(result: dict, recent_topics: list[dict] | None = None) -> dict:
    recent_topics = recent_topics or []
    candidate_tokens = _tokenize_topic(
        " ".join(
            [
                result.get("title", ""),
                result.get("recommended_angle", ""),
                result.get("strategy_cluster", ""),
                result.get("pillar_topic", ""),
            ]
        )
    )
    if not candidate_tokens or not recent_topics:
        return {"penalty": 0, "matched_recent_topic": None, "overlap_ratio": 0.0}

    best_match = None
    best_overlap = 0.0
    for topic in recent_topics:
        tokens = topic.get("tokens") or set()
        if not tokens:
            continue
        overlap = len(candidate_tokens & tokens) / max(1, min(len(candidate_tokens), len(tokens)))
        if overlap > best_overlap:
            best_overlap = overlap
            best_match = topic

    if best_overlap >= 0.55:
        penalty = 4
    elif best_overlap >= 0.40:
        penalty = 2
    else:
        penalty = 0

    return {
        "penalty": penalty,
        "matched_recent_topic": (
            {
                "title": best_match.get("title"),
                "path": best_match.get("path"),
                "age_days": best_match.get("age_days"),
            }
            if penalty and best_match
            else None
        ),
        "overlap_ratio": round(best_overlap, 2),
    }


def _passes_cluster_gate(result: dict) -> bool:
    evidence = _article_evidence(result)
    cluster = result.get("strategy_cluster", "")
    text = evidence["early_content"]

    if cluster == "storm_damage":
        return bool(
            _matched_terms(text, ["storm", "hail", "wind", "thunderstorm", "tornado", "weather"])
            and _matched_terms(text, ["roof", "home", "house", "property", "tree", "damage", "inspection"])
        )

    if cluster == "ga_insurance_navigation":
        return bool(
            _matched_terms(text, ["insurance", "claim", "deductible", "policy", "rcv", "acv", "hb511", "house bill 511"])
            and _matched_terms(text, ["home", "homeowners", "roof", "storm", "property insurance"])
        )

    if cluster == "roof_safety":
        return bool(
            _matched_terms(text, ["fire", "safety", "unsafe", "structural", "inspection", "hvac", "attic", "ventilation"])
            and _matched_terms(text, ["roof", "home", "house", "building", "construction", "structure", "attic", "hvac"])
        )

    if cluster == "county_guides":
        return bool(
            _matched_terms(text, ["fulton", "dekalb", "cobb", "gwinnett", "cherokee", "county"])
            and _matched_terms(text, ["roof", "permit", "storm", "hail", "wind", "insurance", "replacement", "repair"])
        )

    return False


def _quality_score(result: dict, recent_topics: list[dict] | None = None) -> tuple[float, dict[str, object]]:
    evidence = _article_evidence(result)
    cluster = result.get("strategy_cluster", "")
    cluster_terms = CLUSTER_TERMS.get(cluster, TOPIC_TERMS)

    local_title = _matched_terms(evidence["title_url"], LOCAL_TERMS)
    local_early = _matched_terms(evidence["early_content"], LOCAL_TERMS)
    topic_title = _matched_terms(evidence["title_url"], TOPIC_TERMS)
    topic_early = _matched_terms(evidence["early_content"], TOPIC_TERMS)
    cluster_title = _matched_terms(evidence["title_url"], cluster_terms)
    cluster_early = _matched_terms(evidence["early_content"], cluster_terms)
    territory = _territory_alignment(result)
    semantic = _semantic_relevance(result)
    off_topic_penalty, off_topic_matches = _off_topic_penalty(result)
    duplicate = _duplicate_topic_penalty(result, recent_topics)
    recency = _recency_score(result)
    headline_homeowner = _headline_homeowner_score(result)
    seasonal = _seasonal_bonus(result)
    content_depth = _content_depth_score(result)
    actionability = _actionability_score(result)

    local_score = 3 if local_title else 2 if local_early else 0
    topic_score = 4 if topic_title else 2 if topic_early else 0
    cluster_score = 3 if cluster_title else 2 if cluster_early else 0
    source_score = 2 if result.get("priority_source") else 1 if result.get("secondary_source") else 0
    tavily_score = 1 if float(result.get("tavily_score") or 0) >= 0.2 else 0
    territory_score = float(territory["score"]) * 0.45
    semantic_score = float(semantic["score"]) * 0.35
    duplicate_penalty = int(duplicate["penalty"])

    matched = {
        "local_terms": sorted(set(local_title + local_early)),
        "topic_terms": sorted(set(topic_title + topic_early)),
        "cluster_terms": sorted(set(cluster_title + cluster_early)),
        "territory_alignment": territory,
        "semantic_relevance": semantic,
        "off_topic": {
            "penalty": off_topic_penalty,
            "matched_categories": off_topic_matches,
        },
        "duplicate_topic": duplicate,
        "recency_score": recency,
        "headline_homeowner_score": headline_homeowner,
        "seasonal_bonus": seasonal,
        "content_depth_score": content_depth,
        "actionability_score": actionability,
    }
    score = (
        local_score
        + topic_score
        + cluster_score
        + source_score
        + tavily_score
        + territory_score
        + semantic_score
        + recency
        + headline_homeowner
        + seasonal
        + content_depth
        + actionability
        - off_topic_penalty
        - duplicate_penalty
    )
    return round(score, 2), matched


def _is_relevant_candidate(
    result: dict,
    recent_topics: list[dict] | None = None,
    *,
    min_quality_score: float = DEFAULT_MIN_QUALITY_SCORE,
    quality_score: float | None = None,
    matched: dict[str, object] | None = None,
) -> bool:
    if _is_disqualified(result):
        return False

    if not _is_within_stage_window(result):
        return False

    if not _passes_cluster_gate(result):
        return False

    if quality_score is None or matched is None:
        quality_score, matched = _quality_score(result, recent_topics)
    semantic = matched["semantic_relevance"]
    territory = matched["territory_alignment"]
    return bool(
        matched["local_terms"]
        and (matched["cluster_terms"] or territory["matched_territories"])
        and semantic["passes"]
        and quality_score >= min_quality_score
    )


def _normalize_result(item: dict, search_item: dict, stage: dict) -> dict:
    url = item.get("url", "").strip()
    published_date = item.get("published_date") or item.get("publishedDate") or ""

    return {
        "title": item.get("title", "").strip(),
        "url": url,
        "domain": _source_domain(url),
        "content": item.get("content", "").strip(),
        "published_date": published_date,
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


def search_roofing_news(
    max_results_per_query: int = DEFAULT_MAX_RESULTS_PER_QUERY,
    days_back: int = DEFAULT_DAYS_BACK,
    target_results: int = DEFAULT_TARGET_RESULTS,
    *,
    all_stages: bool = False,
    skip_used_sources: bool = True,
    min_quality_score: float = DEFAULT_MIN_QUALITY_SCORE,
    queries_per_cluster: int = DEFAULT_QUERIES_PER_CLUSTER,
    use_all_queries: bool = False,
    rotation_week: int | None = None,
) -> list[dict]:
    """
    Run all search queries and return deduplicated Tavily results.

    Each result dict contains:
        title, url, domain, content, published_date, tavily_score,
        priority_source, secondary_source, official_source, query,
        strategy_cluster, pillar_topic, trigger_window_hours, retrieved_at
    """
    load_dotenv(PROJECT_ROOT / ".env")
    client = _load_client()
    recent_topics = _recent_draft_topics()
    if recent_topics:
        print(f"[search] Loaded {len(recent_topics)} recent draft topics for duplicate penalties")

    blocked_urls: set[str] = set()
    if skip_used_sources:
        blocked_urls = used_source_urls()
        if blocked_urls:
            print(f"[search] Skipping {len(blocked_urls)} previously used source URL(s)")

    active_plan = build_active_search_plan(
        queries_per_cluster=queries_per_cluster,
        use_all_queries=use_all_queries,
        rotation_week=rotation_week,
    )
    query_count = len(active_plan)
    max_credits = estimate_tavily_credits(query_count, len(SEARCH_STAGES))
    if use_all_queries or queries_per_cluster <= 0:
        print(
            f"[search] Plan: {query_count} queries across {len(SEARCH_STAGES)} stages "
            f"(target {target_results} kept results, max ~{max_credits} Tavily credits if all stages run)"
        )
    else:
        week_number = rotation_week or datetime.now(timezone.utc).isocalendar().week
        print(
            f"[search] Plan: {query_count} active queries ({queries_per_cluster}/cluster, ISO week {week_number}) "
            f"from {len(SEARCH_PLAN)} total across {len(SEARCH_STAGES)} stages "
            f"(target {target_results}, max ~{max_credits} credits if all stages run)"
        )

    results_by_url: dict[str, dict] = {}
    stages = [
        {
            **stage,
            "days": days_back if stage["name"] == "priority_7_day_news" else stage["days"],
            "max_results_per_query": max_results_per_query
            if stage["name"] == "priority_7_day_news"
            else stage["max_results_per_query"],
        }
        for stage in SEARCH_STAGES
    ]
    queries_run = 0
    skipped_used_sources = 0

    for stage in stages:
        print(f"[search] Running stage: {stage['name']}")
        for search_item in active_plan:
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
                print(f"[search] Query failed for {query!r}: {exc}")
                continue

            for item in response.get("results", []):
                url = item.get("url", "").strip()
                if not url:
                    continue

                if blocked_urls and normalize_source_url(url) in blocked_urls:
                    skipped_used_sources += 1
                    continue

                result = _normalize_result(item, search_item, stage)
                quality_score, matched = _quality_score(result, recent_topics)
                result["search_quality_score"] = quality_score
                result["matched_terms"] = matched
                result["territory_alignment_score"] = matched["territory_alignment"]["score"]
                result["matched_territories"] = matched["territory_alignment"]["matched_territories"]
                result["multi_territory_bonus"] = matched["territory_alignment"]["multi_territory_bonus"]
                result["semantic_relevance_score"] = matched["semantic_relevance"]["score"]
                result["semantic_relevance_rules"] = sorted(matched["semantic_relevance"]["matched_rules"].keys())
                result["off_topic_penalty"] = matched["off_topic"]["penalty"]
                result["off_topic_matches"] = matched["off_topic"]["matched_categories"]
                result["duplicate_topic_penalty"] = matched["duplicate_topic"]["penalty"]
                result["duplicate_topic_match"] = matched["duplicate_topic"]["matched_recent_topic"]
                result["duplicate_topic_overlap"] = matched["duplicate_topic"]["overlap_ratio"]
                result["recency_score"] = matched["recency_score"]
                result["headline_homeowner_score"] = matched["headline_homeowner_score"]
                result["seasonal_bonus"] = matched["seasonal_bonus"]
                result["content_depth_score"] = matched["content_depth_score"]
                result["actionability_score"] = matched["actionability_score"]

                if not _is_relevant_candidate(
                    result,
                    recent_topics,
                    min_quality_score=min_quality_score,
                    quality_score=quality_score,
                    matched=matched,
                ):
                    continue

                existing = results_by_url.get(url)
                if not existing or result["search_quality_score"] > existing["search_quality_score"]:
                    results_by_url[url] = result

            if not all_stages and len(results_by_url) >= target_results:
                print(
                    f"[search] Target of {target_results} reached mid-stage — "
                    f"skipping remaining queries in {stage['name']}"
                )
                break

        print(f"[search] Stage {stage['name']} total kept so far: {len(results_by_url)}")
        if not all_stages and len(results_by_url) >= target_results:
            print(f"[search] Target of {target_results} reached — stopping early")
            break

    results = list(results_by_url.values())

    results.sort(
        key=lambda result: (
            result["priority_source"],
            result.get("secondary_source", False),
            result.get("official_source", False),
            result["search_quality_score"],
            result.get("recency_score", 0),
            result["strategy_cluster"] != "county_guides",
            result["tavily_score"],
        ),
        reverse=True,
    )

    credits_used = queries_run * TAVILY_ADVANCED_SEARCH_CREDITS
    skipped_note = f", skipped {skipped_used_sources} previously used" if skipped_used_sources else ""
    print(
        f"[search] Found {len(results)} unique results "
        f"from {query_count} active queries "
        f"({queries_run} API calls, ~{credits_used} Tavily credits{skipped_note})"
    )
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
    print(f"[search] Results saved to {output_path}")
    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search Metro Atlanta roofing news with Tavily.")
    parser.add_argument(
        "--target-results",
        type=int,
        default=DEFAULT_TARGET_RESULTS,
        help=f"Stop after this many kept results unless --all-stages is set (default: {DEFAULT_TARGET_RESULTS}).",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=DEFAULT_DAYS_BACK,
        help=f"Days back for the priority 7-day stage (default: {DEFAULT_DAYS_BACK}).",
    )
    parser.add_argument(
        "--max-results-per-query",
        type=int,
        default=DEFAULT_MAX_RESULTS_PER_QUERY,
        help=f"Max Tavily results for the priority 7-day stage only (default: {DEFAULT_MAX_RESULTS_PER_QUERY}).",
    )
    parser.add_argument(
        "--all-stages",
        action="store_true",
        help="Run every search stage even after --target-results is reached.",
    )
    parser.add_argument(
        "--include-used-sources",
        action="store_true",
        help="Allow URLs already recorded in output/sources/used_sources.json.",
    )
    parser.add_argument(
        "--min-quality-score",
        type=float,
        default=DEFAULT_MIN_QUALITY_SCORE,
        help=f"Minimum search_quality_score to keep a candidate (default: {DEFAULT_MIN_QUALITY_SCORE}).",
    )
    parser.add_argument(
        "--queries-per-cluster",
        type=int,
        default=DEFAULT_QUERIES_PER_CLUSTER,
        help=(
            f"Rotating query subset per strategy cluster (default: {DEFAULT_QUERIES_PER_CLUSTER}). "
            "Use --all-queries to run every configured query."
        ),
    )
    parser.add_argument(
        "--all-queries",
        action="store_true",
        help="Run all strategy queries instead of the weekly rotating subset.",
    )
    parser.add_argument(
        "--rotation-week",
        type=int,
        help="ISO week number for query rotation (default: current UTC week).",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Peachtree Blog Pipeline - search.py test")
    print(f"Searching for Metro Atlanta roofing news from the past {args.days_back} days")
    print("=" * 60)

    try:
        results = search_roofing_news(
            max_results_per_query=args.max_results_per_query,
            days_back=args.days_back,
            target_results=args.target_results,
            all_stages=args.all_stages,
            skip_used_sources=not args.include_used_sources,
            min_quality_score=args.min_quality_score,
            queries_per_cluster=args.queries_per_cluster,
            use_all_queries=args.all_queries,
            rotation_week=args.rotation_week,
        )
    except (EnvironmentError, RuntimeError) as exc:
        print(f"\n[search] Setup needed: {exc}")
        raise SystemExit(1) from exc

    if not results:
        save_results(results)
        print("\n[!] No relevant results returned. Try widening days_back or broadening sources.")
    else:
        print(f"\nTop results:\n")
        for i, r in enumerate(results[:10], 1):
            print(f"  {i}. {r['title']}")
            print(f"     {r['url']}")
            print(f"     Published: {r['published_date'] or 'unknown'}")
            print(f"     Strategy cluster: {r['strategy_cluster']}")
            print(f"     Priority source: {r['priority_source']}")
            print(f"     Secondary source: {r.get('secondary_source', False)}")
            print()

        save_results(results)
        print(f"\n[search] Test complete - {len(results)} results ready for evaluate.py")

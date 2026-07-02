import re
from dataclasses import dataclass

from app.models import Account, Opportunity, Product, RecommendationOption
from app.tools.text_matching import contains_phrase, unique_sorted


BADGE_ORDER = ["Best", "Better", "Good"]
BUDGET_PATTERN = re.compile(r"(?:under|below|less than|<=|\$)\s*\$?([0-9][0-9,]*)", re.I)

FEATURE_SYNONYMS = {
    "battery": ["battery", "long battery", "all day"],
    "budget": ["budget", "affordable", "low cost", "under", "below"],
    "cad": ["cad", "architecture", "engineering", "rendering"],
    "classroom": ["classroom", "student", "school", "lab"],
    "docking": ["dock", "docking", "desk setup"],
    "durable": ["durable", "rugged", "shared"],
    "graphics": ["graphics", "gpu", "discrete", "render"],
    "manageability": ["manageability", "managed", "fleet", "standardize"],
    "memory": ["memory", "ram", "64gb", "128gb"],
    "performance": ["performance", "powerful", "compute", "ai"],
    "portable": ["portable", "lightweight", "travel", "mobile", "roaming"],
    "security": ["security", "secure", "compliance"],
    "touch": ["touch", "tablet", "2-in-1", "convertible", "pen"],
    "video": ["video", "camera", "conference", "hybrid"],
    "workstation": ["workstation", "engineering", "creator", "architect"],
}


@dataclass(frozen=True)
class ProductScore:
    """Intermediate score before converting to API response models."""

    product: Product
    score: float
    matched_requirements: list[str]
    reasoning: str


# Keep scoring in a class so the workflow service has a small dependency.
class RecommendationEngine:
    """Deterministic recommender backed by local JSON catalog data."""

    def recommend(
        self,
        query: str,
        products: list[Product],
        account: Account | None,
        opportunity: Opportunity | None,
        limit: int = 3,
    ) -> list[RecommendationOption]:
        """Return ranked recommendations for a user query."""
        # Extract requirements from the request and selected opportunity.
        requirements = _extract_requirements(query, opportunity)
        budget_limit = _extract_budget(query)

        # Score every product before applying the top-card display limit.
        scored_products = [
            _score_product(product, requirements, budget_limit, account)
            for product in products
        ]

        # Return the top results with stable badge labels.
        ranked_products = sorted(
            scored_products,
            key=lambda item: (item.score, -item.product.price_usd),
            reverse=True,
        )
        return _build_options(ranked_products[:limit])


# Convert ranked internal scores to the public recommendation model.
def _build_options(scored_products: list[ProductScore]) -> list[RecommendationOption]:
    options: list[RecommendationOption] = []
    for index, scored_product in enumerate(scored_products):
        badge = BADGE_ORDER[index] if index < len(BADGE_ORDER) else "Consider"
        options.append(
            RecommendationOption(
                product=scored_product.product,
                score=round(scored_product.score, 1),
                badge=badge,
                matched_requirements=scored_product.matched_requirements,
                reasoning=scored_product.reasoning,
            )
        )
    return options


# Score a product against extracted needs and simple account availability.
def _score_product(
    product: Product,
    requirements: list[str],
    budget_limit: int | None,
    account: Account | None,
) -> ProductScore:
    product_text = _product_text(product)
    matched_requirements = _match_requirements(requirements, product_text)
    score = 45.0 + len(matched_requirements) * 12
    score += _score_hardware_fit(product, requirements)
    score += _score_budget_fit(product, budget_limit)
    score += _score_country_fit(product, account)
    reasoning = _build_reasoning(product, matched_requirements, budget_limit, account)
    return ProductScore(product, score, matched_requirements, reasoning)


# Build the searchable text for a product from catalog fields.
def _product_text(product: Product) -> str:
    fields = [
        product.name,
        product.category,
        product.family,
        product.form_factor,
        product.summary,
        product.specs.gpu,
        product.specs.display,
        *product.personas,
        *product.use_cases,
        *product.tags,
    ]
    return " ".join(fields).lower()


# Extract canonical requirement terms from user and opportunity context.
def _extract_requirements(query: str, opportunity: Opportunity | None) -> list[str]:
    source_text = query
    if opportunity:
        source_text = " ".join(
            [query, opportunity.summary, *opportunity.priority_requirements]
        )

    # Map user language to the small canonical requirement vocabulary.
    matched_terms = [
        feature
        for feature, synonyms in FEATURE_SYNONYMS.items()
        if any(contains_phrase(source_text, synonym) for synonym in synonyms)
    ]
    return unique_sorted(matched_terms) or ["manageability", "security", "video"]


# Pull a rough budget ceiling from natural language.
def _extract_budget(query: str) -> int | None:
    match = BUDGET_PATTERN.search(query)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


# Check which canonical requirements appear in the product record.
def _match_requirements(requirements: list[str], product_text: str) -> list[str]:
    matched = []
    for term in requirements:
        synonyms = FEATURE_SYNONYMS.get(term, []) + [term]
        if any(contains_phrase(product_text, synonym) for synonym in synonyms):
            matched.append(term)
    return unique_sorted(matched)


# Add targeted hardware boosts for requirements that need numeric fields.
def _score_hardware_fit(product: Product, requirements: list[str]) -> float:
    score = 0.0
    if "battery" in requirements and product.specs.battery_hours >= 12:
        score += 8
    if "memory" in requirements and product.specs.memory_gb >= 64:
        score += 10
    if "graphics" in requirements and "rtx" in product.specs.gpu.lower():
        score += 10
    if "portable" in requirements and product.specs.weight_kg <= 1.3:
        score += 8
    return score


# Reward products under budget and apply a small penalty above budget.
def _score_budget_fit(product: Product, budget_limit: int | None) -> float:
    if budget_limit is None:
        return 0.0
    if product.price_usd <= budget_limit:
        return 10.0
    return -min((product.price_usd - budget_limit) / 100, 18.0)


# Reward products available in the selected account country.
def _score_country_fit(product: Product, account: Account | None) -> float:
    if account is None:
        return 0.0
    if account.country in product.inventory.countries:
        return 6.0
    return -12.0


# Turn scoring evidence into card-ready reasoning text.
def _build_reasoning(
    product: Product,
    matched_requirements: list[str],
    budget_limit: int | None,
    account: Account | None,
) -> str:
    reason_parts = _build_reason_parts(product, matched_requirements)
    if budget_limit and product.price_usd <= budget_limit:
        reason_parts.append(f"fits the ${budget_limit:,} budget target")
    if account and account.country in product.inventory.countries:
        reason_parts.append(f"available in {account.country}")
    return "; ".join(reason_parts) + "."


# Keep the reasoning phrase concise even when many terms match.
def _build_reason_parts(product: Product, matched_requirements: list[str]) -> list[str]:
    if not matched_requirements:
        return [product.summary]
    visible_terms = ", ".join(matched_requirements[:4])
    return [f"matches {visible_terms}", product.summary]

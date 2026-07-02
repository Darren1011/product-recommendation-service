import re


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


# Normalize text once before token-level matching.
def tokenize_text(text: str) -> set[str]:
    """Return lowercase alphanumeric tokens from free text."""
    return set(TOKEN_PATTERN.findall(text.lower()))


# Normalize a list of phrases into a flat token set.
def tokenize_phrases(phrases: list[str]) -> set[str]:
    """Return tokens across multiple short phrases."""
    tokens: set[str] = set()
    for phrase in phrases:
        tokens.update(tokenize_text(phrase))
    return tokens


# Use substring matching for user-facing concepts such as "battery life".
def contains_phrase(text: str, phrase: str) -> bool:
    """Check whether a normalized phrase appears in normalized text."""
    normalized_text = " ".join(TOKEN_PATTERN.findall(text.lower()))
    normalized_phrase = " ".join(TOKEN_PATTERN.findall(phrase.lower()))
    return normalized_phrase in normalized_text


# Keep user-visible matched terms stable and sorted.
def unique_sorted(values: list[str]) -> list[str]:
    """Return case-preserving values deduplicated by lowercase form."""
    seen_values: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        normalized_value = value.lower()
        if normalized_value in seen_values:
            continue
        seen_values.add(normalized_value)
        unique_values.append(value)
    return sorted(unique_values, key=str.lower)

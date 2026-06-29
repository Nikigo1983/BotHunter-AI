import math
import re
from collections import Counter

FORBIDDEN_WORDS: frozenset[str] = frozenset(
    {"crypto", "bonus", "airdrop", "casino", "bet", "forex", "trade"}
)

DICTIONARY_WORDS: frozenset[str] = frozenset(
    {
        "admin",
        "support",
        "official",
        "manager",
        "agent",
        "service",
        "help",
        "user",
        "bot",
        "channel",
    }
)

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F900-\U0001F9FF"
    "\U00002702-\U000027B0"
    "]+",
    flags=re.UNICODE,
)

LATIN_PATTERN = re.compile(r"[A-Za-z]")
CYRILLIC_PATTERN = re.compile(r"[А-Яа-яЁё]")
UPPERCASE_PATTERN = re.compile(r"[A-ZА-ЯЁ]")


def get_display_name(first_name: str | None, last_name: str | None) -> str:
    parts = [first_name or "", last_name or ""]
    return " ".join(part.strip() for part in parts if part and part.strip()).strip()


def count_digits(value: str) -> int:
    return sum(char.isdigit() for char in value)


def max_consecutive_digits(value: str) -> int:
    current = 0
    maximum = 0
    for char in value:
        if char.isdigit():
            current += 1
            maximum = max(maximum, current)
        else:
            current = 0
    return maximum


def count_emoji(value: str) -> int:
    return sum(len(match.group()) for match in EMOJI_PATTERN.finditer(value))


def contains_words(value: str, words: frozenset[str]) -> bool:
    lowered = value.lower()
    return any(word in lowered for word in words)


def calculate_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = Counter(value)
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def calculate_letter_ratio(value: str, pattern: re.Pattern[str]) -> float:
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return 0.0
    matches = len(pattern.findall(value))
    return matches / len(letters)


def calculate_uppercase_ratio(value: str) -> float:
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return 0.0
    uppercase_count = len(UPPERCASE_PATTERN.findall(value))
    return uppercase_count / len(letters)


def has_mixed_alphabet(value: str) -> bool:
    has_latin = bool(LATIN_PATTERN.search(value))
    has_cyrillic = bool(CYRILLIC_PATTERN.search(value))
    return has_latin and has_cyrillic


def contains_random_sequence(value: str, entropy: float) -> bool:
    if len(value) < 8:
        return False
    if entropy < 3.5:
        return False
    consonant_runs = re.findall(r"[^aeiouAEIOUаеёиоуыэюяАЕЁИОУЫЭЮЯ0-9_]{5,}", value)
    return bool(consonant_runs) or entropy >= 4.0

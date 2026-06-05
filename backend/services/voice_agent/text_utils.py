"""
Text Utilities for Voice Agent.

Provides text normalization utilities for voice input:
- Convert spoken numbers to digits
- Normalize names (remove titles, common variations)
- Strip markdown and control signals from TTS output
"""

import re
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# SPOKEN NUMBER TO DIGIT CONVERSION
# =============================================================================

SPOKEN_DIGITS = {
    "zero": "0", "oh": "0", "o": "0",
    "one": "1",
    "two": "2", "to": "2", "too": "2",
    "three": "3",
    "four": "4", "for": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}

# Number words that might appear in phone numbers
SPOKEN_TENS = {
    "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
    "eighteen": "18", "nineteen": "19",
    "twenty": "20", "thirty": "30", "forty": "40", "fifty": "50",
    "sixty": "60", "seventy": "70", "eighty": "80", "ninety": "90",
}


def normalize_phone_number(spoken_phone: str) -> str:
    """
    Convert spoken phone number to digit format.
    
    Examples:
        "o four nine three one three two five" -> "04931325"
        "0493132525" -> "0493132525"
        "oh four double nine three one two five" -> "0499312-5"
        "+61 493 132 525" -> "+61493132525"
    
    Args:
        spoken_phone: Phone number as spoken or in various formats
        
    Returns:
        Normalized phone number with only digits (and optional + prefix)
    """
    if not spoken_phone:
        return ""
    
    # Convert to lowercase for matching
    text = spoken_phone.lower().strip()
    
    # Handle "double" and "triple" patterns
    # "double five" -> "55", "triple one" -> "111"
    text = re.sub(r'\bdouble\s+(\w+)', lambda m: convert_word_to_digit(m.group(1)) * 2, text)
    text = re.sub(r'\btriple\s+(\w+)', lambda m: convert_word_to_digit(m.group(1)) * 3, text)
    
    # Split into words and convert each
    words = text.split()
    result = []
    
    for word in words:
        # Clean the word
        clean_word = re.sub(r'[^\w+]', '', word)
        
        if clean_word.startswith('+'):
            result.append('+')
            clean_word = clean_word[1:]
        
        if clean_word.isdigit():
            result.append(clean_word)
        elif clean_word in SPOKEN_DIGITS:
            result.append(SPOKEN_DIGITS[clean_word])
        elif clean_word in SPOKEN_TENS:
            result.append(SPOKEN_TENS[clean_word])
        # Skip non-numeric words entirely
    
    return ''.join(result)


def is_valid_au_phone(phone: str) -> tuple[bool, str]:
    """
    Validate if a phone number is a valid Australian format.
    
    Valid formats:
    - 04XX XXX XXX (10 digits, mobile)
    - +614XX XXX XXX (11/12 digits with country code)
    - 03 XXXX XXXX (10 digits, landline)
    
    Args:
        phone: Phone number (can be spoken words or digits)
        
    Returns:
        Tuple of (is_valid, message)
        - If valid: (True, "")
        - If invalid: (False, "reason for rejection")
    """
    # First normalize to digits
    normalized = normalize_phone_number(phone)
    
    if not normalized:
        return False, "I didn't catch a phone number. Could you say it again slowly?"
    
    # Remove country code prefix for length check
    digits_only = normalized.lstrip('+')
    
    # Handle +61 prefix (11 digits is valid: 61 + 9 remaining)
    if digits_only.startswith('61'):
        digits_for_length = digits_only[2:]  # Remove country code
    else:
        digits_for_length = digits_only
    
    # Australian mobile numbers (04xx) MUST be exactly 10 digits
    if digits_for_length.startswith('04') or digits_only.startswith('614'):
        if len(digits_for_length) != 10:
            return False, f"Australian mobile numbers need exactly 10 digits. I got {len(digits_for_length)}. Could you repeat all 10 digits starting with 04?"
    elif len(digits_for_length) < 10:
        missing = 10 - len(digits_for_length)
        return False, f"That phone number seems too short - I got {len(digits_for_length)} digits. Could you repeat all 10 digits?"
    
    if len(digits_only) > 12:
        return False, f"That phone number seems too long ({len(digits_only)} digits). Could you repeat it more slowly?"
    
    # Check valid Australian prefixes
    valid_prefixes = ['04', '614', '61', '02', '03', '07', '08']
    has_valid_prefix = any(digits_only.startswith(p) for p in valid_prefixes)
    
    if not has_valid_prefix and len(digits_only) >= 10:
        # Might be missing leading zero
        return False, "That doesn't look like an Australian number. Should it start with 04 for mobile or 03 for landline?"
    
    # Valid!
    return True, ""


def convert_word_to_digit(word: str) -> str:
    """Convert a single word to digit(s)."""
    word = word.lower()
    if word in SPOKEN_DIGITS:
        return SPOKEN_DIGITS[word]
    if word in SPOKEN_TENS:
        return SPOKEN_TENS[word]
    if word.isdigit():
        return word
    return ""


# =============================================================================
# NAME NORMALIZATION
# =============================================================================

TITLE_PREFIXES = [
    "mr", "mr.", "mister", 
    "mrs", "mrs.", "missus",
    "ms", "ms.", "miss",
    "dr", "dr.", "doctor",
    "prof", "prof.", "professor",
    "sir", "madam", "ma'am",
]


def normalize_guest_name(spoken_name: str) -> str:
    """
    Normalize a guest name for matching.
    
    Removes titles, extra whitespace, and normalizes case.
    
    Examples:
        "mister Mohan" -> "mohan"
        "Mr. John Smith" -> "john smith"
        "  Ms. Jane   Doe  " -> "jane doe"
    
    Args:
        spoken_name: Name as spoken with possible title
        
    Returns:
        Normalized name for fuzzy matching
    """
    if not spoken_name:
        return ""
    
    # Lowercase and strip
    name = spoken_name.lower().strip()
    
    # Remove title prefixes
    for title in TITLE_PREFIXES:
        # Match title at start with optional punctuation
        pattern = rf'^{re.escape(title)}\.?\s+'
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)
    
    # Remove extra whitespace
    name = ' '.join(name.split())
    
    return name


def fuzzy_name_match(search_name: str, stored_name: str, threshold: float = 0.6) -> bool:
    """
    Check if two names match with fuzzy logic.
    
    Handles:
    - Partial matches (first name only)
    - Minor spelling differences
    - Title variations
    
    Args:
        search_name: Name being searched for
        stored_name: Name stored in database
        threshold: Minimum similarity ratio (0-1)
        
    Returns:
        True if names match within threshold
    """
    # Normalize both names
    search = normalize_guest_name(search_name)
    stored = normalize_guest_name(stored_name)
    
    if not search or not stored:
        return False
    
    # Exact match after normalization
    if search == stored:
        return True
    
    # One contains the other (partial name match)
    if search in stored or stored in search:
        return True
    
    # Check individual words match
    search_words = set(search.split())
    stored_words = set(stored.split())
    
    # If any word matches exactly, consider it a match
    if search_words & stored_words:
        return True
    
    # Simple character-based similarity
    # Using Jaccard similarity on character level
    search_chars = set(search.replace(' ', ''))
    stored_chars = set(stored.replace(' ', ''))
    
    if not search_chars or not stored_chars:
        return False
    
    intersection = len(search_chars & stored_chars)
    union = len(search_chars | stored_chars)
    similarity = intersection / union
    
    return similarity >= threshold


# =============================================================================
# TTS OUTPUT CLEANING
# =============================================================================

# Control signals that should be stripped, not spoken
CONTROL_SIGNALS = [
    "[[HANGUP]]",
    "[[END_CALL]]",
    "[[TRANSFER]]",
]

# Markdown patterns to clean
MARKDOWN_PATTERNS = [
    # ── Unicode smart punctuation (bleeds into TTS if not caught) ──────────
    ('\u2019', "'"),   # right single quotation mark → apostrophe
    ('\u2018', "'"),   # left single quotation mark → apostrophe
    ('\u201c', '"'),   # left double quotation mark → straight quote
    ('\u201d', '"'),   # right double quotation mark → straight quote
    ('\u2014', ', '),  # em dash → comma-space (natural pause in speech)
    ('\u2013', '-'),   # en dash → hyphen
    ('\u2026', '...'), # ellipsis character → three dots
    ('\n\n', '. '),    # paragraph break → sentence ending + space
    ('\n', ' '),       # single newline → space
    # ── Markdown formatting ─────────────────────────────────────────────────
    (r'\[System Note:.*?\]', ''),         # [System Note: ...] -> remove
    (r'\*\*(.+?)\*\*', r'\1'),           # **bold** -> bold
    (r'\*(.+?)\*', r'\1'),                # *italic* -> italic
    (r'__(.+?)__', r'\1'),                # __bold__ -> bold
    (r'_(.+?)_', r'\1'),                  # _italic_ -> italic
    (r'~~(.+?)~~', r'\1'),                # ~~strike~~ -> strike
    (r'`(.+?)`', r'\1'),                  # `code` -> code
    (r'#{1,6}\s*', ''),                   # # headers -> remove
    (r'\[([^\]]+)\]\([^\)]+\)', r'\1'),   # [text](url) -> text
    (r'\!\[([^\]]*)\]\([^\)]+\)', ''),    # ![alt](url) -> remove
    (r'^\s*[-*+]\s+', ''),                # - bullet -> remove marker
    (r'^\s*\d+\.\s+', ''),                # 1. numbered -> remove marker
    (r'^\s*>\s*', ''),                    # > quote -> remove marker
    (r'---+', ''),                        # --- horizontal rule
    (r'\|', ' '),                         # | table separator
]


def clean_tts_output(text: str) -> str:
    """
    Clean text for TTS output.

    Removes control signals, unicode smart punctuation, and markdown formatting
    so TTS never reads raw symbols, newlines, or curly quotes aloud.

    Examples:
        "Have a great day! [[HANGUP]]" -> "Have a great day!"
        "Check **this** out" -> "Check this out"
        "It\u2019s available" -> "It's available"
        "Room\\ndetails" -> "Room details"

    Args:
        text: Raw text that might contain control signals, unicode, or markdown

    Returns:
        Clean text suitable for TTS
    """
    if not text:
        return ""

    result = text

    # ── Date ordinal: zero-padded day → spoken ordinal (M1)
    # "June 06" → "June 6th", "July 01" → "July 1st" — prevents TTS reading "zero six"
    import re as _re
    def _to_ordinal(n: int) -> str:
        suf = {1: 'st', 2: 'nd', 3: 'rd'}
        return f"{n}{'th' if 11 <= n <= 13 else suf.get(n % 10, 'th')}"
    result = _re.sub(r'\b0(\d)\b', lambda m: _to_ordinal(int(m.group(1))), result)

    # ── Room type slash normalization (M1 extended: any letter/slash/letter combo)
    # "Queen/Double" → "Queen and Double", "Family/Spa" → "Family and Spa"
    # Prevents TTS speaking "slash" for any room type or combo string
    result = re.sub(r'(?<=[A-Za-z])/(?=[A-Za-z])', ' and ', result)

    # Remove control signals
    for signal in CONTROL_SIGNALS:
        result = result.replace(signal, '')

    # Apply cleaning patterns — split plain-string and regex passes
    for pattern, replacement in MARKDOWN_PATTERNS:
        if isinstance(pattern, str) and not pattern.startswith('(') and not any(c in pattern for c in r'\.^$*+?{}[]|()'):
            # Plain string replacement (unicode chars, literal newlines)
            result = result.replace(pattern, replacement)
        else:
            # Regex replacement — use DOTALL so \n is matched by .
            result = re.sub(pattern, replacement, result, flags=re.MULTILINE | re.DOTALL)

    # IMPORTANT: Remove any remaining standalone markdown symbols
    # This catches cases where ** or * appear without matching pairs
    # or when text is split across multiple chunks
    result = re.sub(r'\*{2,}', '', result)           # ** or more
    result = re.sub(r'(?<!\w)\*(?!\w)', '', result)   # standalone *
    result = re.sub(r'_{2,}', '', result)             # __ or more
    result = re.sub(r'(?<!\w)_(?!\w)', '', result)    # standalone _
    result = re.sub(r'~{2,}', '', result)             # ~~ or more
    result = re.sub(r'`+', '', result)                # ` backticks

    # Clean up extra whitespace (collapses multiple spaces from replacements)
    result = ' '.join(result.split())

    return result.strip()



def extract_control_signals(text: str) -> tuple[str, list[str]]:
    """
    Extract control signals from text and return clean text.
    
    Args:
        text: Text that may contain control signals
        
    Returns:
        Tuple of (clean_text, list_of_signals_found)
    """
    signals_found = []
    clean_text = text
    
    for signal in CONTROL_SIGNALS:
        if signal in text:
            signals_found.append(signal)
            clean_text = clean_text.replace(signal, '')
    
    return clean_text.strip(), signals_found


# =============================================================================
# URL AND SPECIAL CONTENT HANDLING
# =============================================================================

def make_speakable(text: str) -> str:
    """
    Convert text with URLs, emails, and special content into speakable form.
    
    Examples:
        "Visit https://example.com" -> "Visit example dot com"
        "Email us at info@hotel.com" -> "Email us at info at hotel dot com"
        "$130" -> "130 dollars"
    
    Args:
        text: Text with potential special content
        
    Returns:
        Text optimized for speech
    """
    result = text
    
    # Replace URLs with spoken version
    # https://example.com -> "example dot com"
    url_pattern = r'https?://(?:www\.)?([^\s/]+)(?:/[^\s]*)?'
    result = re.sub(url_pattern, lambda m: m.group(1).replace('.', ' dot '), result)
    
    # Replace email addresses
    # info@hotel.com -> "info at hotel dot com"
    email_pattern = r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+)\.([a-zA-Z]{2,})'
    result = re.sub(email_pattern, r'\1 at \2 dot \3', result)
    
    # Replace dollar amounts for cleaner speech
    # $130 -> 130 dollars
    result = re.sub(r'\$(\d+)', r'\1 dollars', result)
    
    # Replace % 
    result = re.sub(r'(\d+)%', r'\1 percent', result)
    
    return result


def prepare_for_tts(text: str) -> tuple[str, list[str]]:
    """
    Full TTS preparation pipeline.
    
    1. Extract control signals
    2. Clean markdown
    3. Make content speakable
    
    Args:
        text: Raw text from LLM
        
    Returns:
        Tuple of (tts_ready_text, control_signals)
    """
    # Extract control signals first
    clean_text, signals = extract_control_signals(text)
    
    # Clean markdown formatting
    clean_text = clean_tts_output(clean_text)
    
    # Make special content speakable
    clean_text = make_speakable(clean_text)
    
    return clean_text, signals

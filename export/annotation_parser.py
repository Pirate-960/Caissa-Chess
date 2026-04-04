"""
export/annotation_parser.py

Parses LLM-generated PGN text into structured move data WITH annotations preserved.

The LLM generates PGN with inline comments ({...}), NAG symbols (!!, ?, etc.), and
sometimes engine evaluations. Previously, the pipeline stripped all of these during
move extraction. This module preserves them as structured data.

Also handles:
- Opening detection by matching move sequences against openings.json
- Header extraction with proper defaults
- Result detection from movetext
- FEN consistency validation
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class ParsedMove:
    """A single move with all its annotations preserved."""
    san: str                                    # SAN notation (e.g., "Nf3", "Bxe5+")
    move_number: int                            # 1-based move number
    is_white: bool                              # True if white's move
    comment: str = ""                           # Comment from {braces}
    nags: List[str] = field(default_factory=list)  # NAG strings: "!!", "?!", "?", etc.
    evaluation: Optional[float] = None          # Engine eval if detected in comment
    clock_time: Optional[str] = None            # Clock time if present


@dataclass
class ParsedGame:
    """Complete parsed game with headers, moves, annotations, and metadata."""
    headers: Dict[str, str] = field(default_factory=dict)
    moves: List[ParsedMove] = field(default_factory=list)
    result: str = "*"
    eco: str = ""
    opening_name: str = ""
    opening_variation: str = ""
    raw_pgn: str = ""

    @property
    def white(self) -> str:
        return self.headers.get("White", "?")

    @property
    def black(self) -> str:
        return self.headers.get("Black", "?")

    @property
    def event(self) -> str:
        return self.headers.get("Event", "Caissa Generated Game")

    @property
    def date(self) -> str:
        return self.headers.get("Date", "????.??.??")

    @property
    def site(self) -> str:
        return self.headers.get("Site", "Caissa Chess Engine")

    @property
    def move_count(self) -> int:
        """Number of full moves (pairs)."""
        if not self.moves:
            return 0
        return self.moves[-1].move_number

    @property
    def has_annotations(self) -> bool:
        """Whether any moves have annotations."""
        return any(m.comment or m.nags for m in self.moves)

    @property
    def san_list(self) -> List[str]:
        """Plain SAN list for backward compatibility."""
        return [m.san for m in self.moves]


# =============================================================================
# NAG PATTERNS
# =============================================================================

# Map of annotation symbols to their standard meanings
NAG_SYMBOL_MAP = {
    "!!": "Brilliant move",
    "!": "Good move",
    "!?": "Interesting move",
    "?!": "Dubious move",
    "?": "Mistake",
    "??": "Blunder",
    "□": "Only move",
}

# Regex: Match NAG symbols that may follow a move (longest first to avoid partial match)
NAG_PATTERN = re.compile(r"(\?\?|\!\!|\!\?|\?\!|\!|\?)")

# Regex: Match evaluation in comments like [+1.23], eval: -0.45, (+2.1), etc.
EVAL_PATTERNS = [
    re.compile(r"\[([+-]?\d+\.?\d*)\]"),                    # [+1.23] or [-0.5]
    re.compile(r"[Ee]val(?:uation)?:\s*([+-]?\d+\.?\d*)"),   # eval: +1.23
    re.compile(r"\(([+-]?\d+\.?\d*)\)"),                     # (+1.23)
    re.compile(r"([+-]?\d+\.?\d*)/\d+"),                     # +1.23/20 (depth notation)
]

# Regex: Clock time in comments like {[%clk 1:23:45]}
CLOCK_PATTERN = re.compile(r"\[%clk\s+([\d:]+)\]")


# =============================================================================
# OPENING DATABASE
# =============================================================================

_openings_cache: Optional[Dict] = None


def _load_openings() -> Dict:
    """Load openings database from data/openings.json."""
    global _openings_cache
    if _openings_cache is not None:
        return _openings_cache

    openings_path = Path(__file__).parent.parent / "data" / "openings.json"
    if openings_path.exists():
        try:
            with open(openings_path, "r", encoding="utf-8") as f:
                _openings_cache = json.load(f)
                logger.debug(f"Loaded {len(_openings_cache)} openings from database")
        except Exception as e:
            logger.warning(f"Failed to load openings database: {e}")
            _openings_cache = {}
    else:
        logger.debug("No openings database found")
        _openings_cache = {}

    return _openings_cache


def detect_opening(moves: List[str]) -> Tuple[str, str, str]:
    """
    Detect the opening by matching move sequences against the database.

    Args:
        moves: List of SAN moves from the game

    Returns:
        (eco_code, opening_name, variation) — empty strings if no match
    """
    openings = _load_openings()
    if not openings or not moves:
        return "", "", ""

    best_match = ("", "", "")
    best_match_length = 0

    for opening_key, opening_data in openings.items():
        opening_moves = opening_data.get("moves", [])
        if not opening_moves:
            continue

        # Check if game moves start with this opening's moves
        match_length = 0
        for i, opening_move in enumerate(opening_moves):
            if i >= len(moves):
                break
            if moves[i] == opening_move:
                match_length = i + 1
            else:
                break

        # Keep the longest (most specific) match
        if match_length > best_match_length and match_length == len(opening_moves):
            eco = opening_data.get("eco", "")
            name = opening_key.replace("_", " ").title()
            notes = opening_data.get("notes", "")
            best_match = (eco, name, notes)
            best_match_length = match_length

    return best_match


# =============================================================================
# MAIN PARSER
# =============================================================================

def parse_pgn(pgn_text: str) -> ParsedGame:
    """
    Parse a PGN string into a ParsedGame with all annotations preserved.

    This is the main entry point. It handles:
    - Header extraction (standard Seven Tag Roster + extras)
    - Comment extraction from {braces}
    - NAG symbol extraction (!, !!, ?, ??, !?, ?!)
    - Evaluation extraction from comments
    - Opening detection
    - Result detection
    - FEN/movetext consistency warning

    Args:
        pgn_text: Raw PGN string from LLM or file

    Returns:
        ParsedGame with full structured data
    """
    if not pgn_text or not pgn_text.strip():
        return ParsedGame(raw_pgn=pgn_text or "")

    game = ParsedGame(raw_pgn=pgn_text)

    # Step 1: Extract headers
    game.headers = _extract_headers(pgn_text)

    # Step 2: Extract movetext (everything after headers)
    movetext = _extract_movetext(pgn_text)

    # Step 3: Detect result
    game.result = _detect_result(movetext, game.headers)

    # Step 4: Parse moves with annotations
    game.moves = _parse_movetext(movetext)

    # Step 5: Detect opening
    san_moves = [m.san for m in game.moves]
    eco, name, variation = detect_opening(san_moves)

    # Use detected opening, or fall back to headers
    game.eco = eco or game.headers.get("ECO", "")
    game.opening_name = name or game.headers.get("Opening", "")
    game.opening_variation = variation or game.headers.get("Variation", "")

    # Step 6: FEN consistency check
    fen = game.headers.get("FEN", "")
    if fen and fen != "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1":
        # Non-standard starting position — if moves start from 1, warn
        if game.moves and game.moves[0].move_number == 1:
            logger.warning(
                "FEN header indicates a non-standard position but moves start from 1. "
                "This may indicate an inconsistent PGN. Removing invalid FEN."
            )
            # Keep a note but remove the misleading FEN
            game.headers.pop("FEN", None)

    # Step 7: Ensure result is in headers
    game.headers["Result"] = game.result

    logger.debug(
        f"Parsed game: {len(game.moves)} moves, "
        f"{sum(1 for m in game.moves if m.comment)} annotated, "
        f"opening={game.opening_name or 'unknown'}, result={game.result}"
    )

    return game


# =============================================================================
# INTERNAL PARSING FUNCTIONS
# =============================================================================

def _extract_headers(pgn_text: str) -> Dict[str, str]:
    """Extract PGN headers into a dictionary."""
    headers = {}
    header_pattern = re.compile(r'\[(\w+)\s+"([^"]*)"\]')

    for match in header_pattern.finditer(pgn_text):
        key = match.group(1)
        value = match.group(2)
        headers[key] = value

    return headers


def _extract_movetext(pgn_text: str) -> str:
    """Extract the movetext portion (everything after the headers block)."""
    lines = pgn_text.strip().split("\n")
    movetext_lines = []
    past_headers = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and not past_headers:
            continue
        elif stripped == "" and not past_headers:
            # Blank line between headers and moves
            past_headers = True
            continue
        else:
            past_headers = True
            if not stripped.startswith("["):
                movetext_lines.append(stripped)

    return " ".join(movetext_lines).strip()


def _detect_result(movetext: str, headers: Dict[str, str]) -> str:
    """Detect game result from movetext or headers."""
    # Check movetext for result marker
    for marker in ["1-0", "0-1", "1/2-1/2"]:
        if marker in movetext:
            return marker

    # Check headers
    result = headers.get("Result", "*")
    if result in ("1-0", "0-1", "1/2-1/2"):
        return result

    return "*"


def _parse_movetext(movetext: str) -> List[ParsedMove]:
    """
    Parse movetext into a list of ParsedMove objects with annotations.

    Handles:
    - Move numbers: "1." "2." "12..."
    - Comments: {This is a comment}
    - NAGs: !! ! ?! ? ?? !?
    - Variations: (parenthesized text) — currently stripped but noted
    - Nested comments and multi-line comments
    """
    if not movetext:
        return []

    moves = []

    # Step 1: Extract comments and replace with placeholders
    comments = []
    comment_map = {}

    def replace_comment(match):
        idx = len(comments)
        comment_text = match.group(1).strip()
        comments.append(comment_text)
        placeholder = f"__COMMENT_{idx}__"
        comment_map[placeholder] = comment_text
        return placeholder

    # Extract {comments} — handle nested braces conservatively
    processed = re.sub(r"\{([^}]*)\}", replace_comment, movetext)

    # Step 2: Remove variations (parentheses) — preserve for future enhancement
    processed = re.sub(r"\([^)]*\)", "", processed)

    # Step 3: Remove result markers from movetext
    processed = re.sub(r"\s*(?:1-0|0-1|1/2-1/2|\*)\s*$", "", processed)

    # Step 4: Tokenize
    tokens = processed.split()

    # Step 5: Walk through tokens and build moves
    current_move_number = 1
    expecting_white = True
    pending_comment_indices = []

    i = 0
    while i < len(tokens):
        token = tokens[i]

        # Skip empty tokens
        if not token.strip():
            i += 1
            continue

        # Check if it's a comment placeholder
        if token.startswith("__COMMENT_") and token.endswith("__"):
            pending_comment_indices.append(token)
            i += 1
            continue

        # Check if it's a move number like "1." or "12..." or "1..."
        move_num_match = re.match(r"^(\d+)(\.{1,3})$", token)
        if move_num_match:
            current_move_number = int(move_num_match.group(1))
            dots = move_num_match.group(2)
            if len(dots) >= 2:
                # "1..." means it's black's move
                expecting_white = False
            else:
                expecting_white = True
            i += 1
            continue

        # Check if token starts with a move number joined with a move:  "1.e4"
        joined_match = re.match(r"^(\d+)\.(\.{0,2})(.+)$", token)
        if joined_match:
            current_move_number = int(joined_match.group(1))
            extra_dots = joined_match.group(2)
            remaining = joined_match.group(3)
            if extra_dots:  # "1...e5" style
                expecting_white = False
            else:
                expecting_white = True
            # Re-insert the remaining part as the current token
            token = remaining
            # Fall through to move parsing below

        # Check if it's a SAN move
        # Include pieces, files, captures, promotion, check/mate, castling
        san_match = re.match(
            r"^([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O(?:-O)?)",
            token
        )

        if san_match:
            san = san_match.group(1)

            # Check for NAGs attached to the move token (after the SAN)
            remainder = token[len(san):]
            nags = []
            while remainder:
                nag_match = NAG_PATTERN.match(remainder)
                if nag_match:
                    nags.append(nag_match.group(1))
                    remainder = remainder[len(nag_match.group(1)):]
                else:
                    break

            # Check subsequent tokens for NAGs
            while i + 1 < len(tokens):
                next_tok = tokens[i + 1]
                if NAG_PATTERN.fullmatch(next_tok):
                    nags.append(next_tok)
                    i += 1
                elif next_tok.startswith("$"):
                    # Numeric NAG like $1, $3
                    nags.append(next_tok)
                    i += 1
                else:
                    break

            # Collect pending comments
            comment_text = ""
            evaluation = None
            clock_time = None

            # Check for comments after the move (next tokens)
            while i + 1 < len(tokens) and tokens[i + 1].startswith("__COMMENT_"):
                pending_comment_indices.append(tokens[i + 1])
                i += 1

            # Also attach any previously pending comments
            if pending_comment_indices:
                all_comments = []
                for cidx in pending_comment_indices:
                    if cidx in comment_map:
                        all_comments.append(comment_map[cidx])
                comment_text = " ".join(all_comments)
                pending_comment_indices = []

                # Try to extract evaluation from comment
                evaluation = _extract_evaluation(comment_text)
                clock_time = _extract_clock_time(comment_text)

            parsed_move = ParsedMove(
                san=san,
                move_number=current_move_number,
                is_white=expecting_white,
                comment=comment_text,
                nags=nags,
                evaluation=evaluation,
                clock_time=clock_time,
            )
            moves.append(parsed_move)

            # Advance state
            if expecting_white:
                expecting_white = False
            else:
                expecting_white = True
                current_move_number += 1

        i += 1

    # Attach any remaining pending comments to the last move
    if pending_comment_indices and moves:
        remaining_comments = []
        for cidx in pending_comment_indices:
            if cidx in comment_map:
                remaining_comments.append(comment_map[cidx])
        if remaining_comments:
            existing = moves[-1].comment
            new_comment = " ".join(remaining_comments)
            moves[-1].comment = f"{existing} {new_comment}".strip() if existing else new_comment

    # Fix move numbers if they seem off (some LLMs number incorrectly)
    _fix_move_numbers(moves)

    return moves


def _fix_move_numbers(moves: List[ParsedMove]) -> None:
    """Ensure move numbers are sequential and correct."""
    expected_number = 1
    expected_white = True

    for move in moves:
        move.move_number = expected_number
        move.is_white = expected_white

        if expected_white:
            expected_white = False
        else:
            expected_white = True
            expected_number += 1


def _extract_evaluation(comment: str) -> Optional[float]:
    """Extract numerical evaluation from a comment string."""
    if not comment:
        return None

    for pattern in EVAL_PATTERNS:
        match = pattern.search(comment)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue

    return None


def _extract_clock_time(comment: str) -> Optional[str]:
    """Extract clock time from a comment string."""
    if not comment:
        return None

    match = CLOCK_PATTERN.search(comment)
    if match:
        return match.group(1)

    return None


# =============================================================================
# UTILITY: FROM PLAIN SAN LIST (backward compatibility)
# =============================================================================

def from_san_list(
    san_moves: List[str],
    headers: Optional[Dict[str, str]] = None,
    result: str = "*",
) -> ParsedGame:
    """
    Create a ParsedGame from a plain list of SAN strings.
    Used for backward compatibility when annotations are not available.

    Args:
        san_moves: List of SAN moves
        headers: Optional PGN headers
        result: Game result

    Returns:
        ParsedGame with moves (no annotations)
    """
    game = ParsedGame(
        headers=headers or {},
        result=result,
    )

    move_number = 1
    is_white = True

    for san in san_moves:
        game.moves.append(ParsedMove(
            san=san,
            move_number=move_number,
            is_white=is_white,
        ))
        if is_white:
            is_white = False
        else:
            is_white = True
            move_number += 1

    # Detect opening
    eco, name, variation = detect_opening(san_moves)
    game.eco = eco
    game.opening_name = name
    game.opening_variation = variation

    # Ensure result in headers
    game.headers["Result"] = result

    return game

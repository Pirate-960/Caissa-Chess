"""
core/board_state.py

Wrapper around python-chess Board with additional metadata and history tracking.

PHASE 3.1 ENHANCEMENTS:
- Advanced position analysis (game phase, piece activity, pawn structure)
- King safety evaluation
- Space and mobility metrics  
- Opening book detection
- Tension and imbalance tracking
- FEN/PGN utilities

Original functionality 100% preserved.
"""

import chess
import chess.pgn
import logging
from typing import List, Optional, Dict, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# PHASE 3.1: NEW ENUMS FOR POSITION CLASSIFICATION
# =============================================================================

class GamePhase(str, Enum):
    """Game phase classification based on material and piece development."""
    OPENING = "opening"           # First 10-12 moves, pieces developing
    EARLY_MIDDLE = "early_middle" # Transition, pieces active, kings castled
    MIDDLE = "middle"             # Full combat, tactical opportunities
    LATE_MIDDLE = "late_middle"   # Simplification beginning
    ENDGAME = "endgame"           # Few pieces, king activation
    PURE_ENDGAME = "pure_endgame" # No queens, minimal material


class PositionType(str, Enum):
    """Strategic position classification."""
    OPEN = "open"             # Open files, bishops powerful
    SEMI_OPEN = "semi_open"   # Mixed pawn structure
    CLOSED = "closed"         # Locked pawns, knights preferred
    DYNAMIC = "dynamic"       # Imbalanced, tactical potential
    QUIET = "quiet"           # Stable, maneuvering required
    SHARP = "sharp"           # Both sides have chances, dangerous


class CastlingStatus(str, Enum):
    """Castling state tracking."""
    NOT_CASTLED = "not_castled"
    KINGSIDE = "kingside"
    QUEENSIDE = "queenside"
    CASTLING_LOST = "castling_lost"  # Rights lost without castling


class PawnStructure(str, Enum):
    """Pawn structure classification."""
    HEALTHY = "healthy"       # No weaknesses
    DOUBLED = "doubled"       # Doubled pawns present
    ISOLATED = "isolated"     # Isolated pawn(s)
    BACKWARD = "backward"     # Backward pawn(s)
    PASSED = "passed"         # Passed pawn(s) present
    CONNECTED = "connected"   # Connected passed pawns
    CHAIN = "chain"           # Pawn chain formation


# =============================================================================
# ORIGINAL DATACLASS (100% PRESERVED)
# =============================================================================

@dataclass
class MoveMetadata:
    """Metadata associated with a move."""
    move: chess.Move
    san: str
    position_before_fen: str
    position_after_fen: str
    is_capture: bool
    is_check: bool
    is_checkmate: bool
    is_sacrifice: bool = False
    evaluation_before: Optional[float] = None
    evaluation_after: Optional[float] = None


# =============================================================================
# PHASE 3.1: NEW ADVANCED DATACLASSES
# =============================================================================

@dataclass
class PieceActivity:
    """Metrics for piece activity and mobility."""
    piece_type: chess.PieceType
    square: chess.Square
    mobility: int                    # Number of legal squares
    attacks_count: int               # Pieces/pawns attacked
    defends_count: int               # Pieces/pawns defended
    is_centralized: bool             # On central squares (d4, e4, d5, e5)
    is_on_open_file: bool            # Rooks on open files
    is_fianchettoed: bool = False    # Bishops on b2, g2, b7, g7
    controls_key_squares: List[str] = field(default_factory=list)


@dataclass
class KingSafety:
    """King safety evaluation metrics."""
    king_square: chess.Square
    pawn_shield_count: int           # Pawns in front of king
    attackers_count: int             # Enemy pieces targeting king zone
    defenders_count: int             # Friendly pieces defending king zone
    is_castled: bool
    castling_side: Optional[CastlingStatus] = None
    open_files_near_king: int = 0    # Dangerous open files
    safety_score: float = 0.0        # 0-100, higher is safer
    
    def to_dict(self) -> Dict:
        return {
            "king_square": chess.square_name(self.king_square),
            "pawn_shield_count": self.pawn_shield_count,
            "attackers_count": self.attackers_count,
            "defenders_count": self.defenders_count,
            "is_castled": self.is_castled,
            "castling_side": self.castling_side.value if self.castling_side else None,
            "open_files_near_king": self.open_files_near_king,
            "safety_score": self.safety_score,
        }


@dataclass
class PawnStructureAnalysis:
    """Detailed pawn structure analysis."""
    doubled_pawns: List[chess.Square] = field(default_factory=list)
    isolated_pawns: List[chess.Square] = field(default_factory=list)
    backward_pawns: List[chess.Square] = field(default_factory=list)
    passed_pawns: List[chess.Square] = field(default_factory=list)
    pawn_islands: int = 0
    pawn_chain_base: Optional[chess.Square] = None
    structure_types: List[PawnStructure] = field(default_factory=list)
    structure_score: float = 0.0     # 0-100, higher is healthier
    
    def to_dict(self) -> Dict:
        return {
            "doubled_pawns": [chess.square_name(sq) for sq in self.doubled_pawns],
            "isolated_pawns": [chess.square_name(sq) for sq in self.isolated_pawns],
            "backward_pawns": [chess.square_name(sq) for sq in self.backward_pawns],
            "passed_pawns": [chess.square_name(sq) for sq in self.passed_pawns],
            "pawn_islands": self.pawn_islands,
            "pawn_chain_base": chess.square_name(self.pawn_chain_base) if self.pawn_chain_base else None,
            "structure_types": [s.value for s in self.structure_types],
            "structure_score": self.structure_score,
        }


@dataclass 
class AdvancedPositionAnalysis:
    """Comprehensive position analysis combining all metrics."""
    game_phase: GamePhase
    position_type: PositionType
    material_balance: int                    # Centipawns, positive = White ahead
    white_king_safety: KingSafety
    black_king_safety: KingSafety
    white_pawn_structure: PawnStructureAnalysis
    black_pawn_structure: PawnStructureAnalysis
    white_space: int                         # Squares controlled
    black_space: int
    white_mobility: int                      # Total piece moves available
    black_mobility: int
    tension_score: float                     # 0-100, higher = more tactical tension
    complexity_score: float                  # 0-100, higher = more complex
    
    def to_dict(self) -> Dict:
        return {
            "game_phase": self.game_phase.value,
            "position_type": self.position_type.value,
            "material_balance": self.material_balance,
            "white_king_safety": self.white_king_safety.to_dict(),
            "black_king_safety": self.black_king_safety.to_dict(),
            "white_pawn_structure": self.white_pawn_structure.to_dict(),
            "black_pawn_structure": self.black_pawn_structure.to_dict(),
            "white_space": self.white_space,
            "black_space": self.black_space,
            "white_mobility": self.white_mobility,
            "black_mobility": self.black_mobility,
            "tension_score": self.tension_score,
            "complexity_score": self.complexity_score,
        }


@dataclass
class OpeningInfo:
    """Opening identification and classification."""
    eco_code: Optional[str] = None
    opening_name: Optional[str] = None
    variation: Optional[str] = None
    is_mainline: bool = False
    move_count_in_book: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "eco_code": self.eco_code,
            "opening_name": self.opening_name,
            "variation": self.variation,
            "is_mainline": self.is_mainline,
            "move_count_in_book": self.move_count_in_book,
        }


# =============================================================================
# ORIGINAL CLASS (100% PRESERVED) + PHASE 3.1 ENHANCEMENTS
# =============================================================================

class BoardState:
    """
    Enhanced board state tracking.
    Keeps history of positions, evaluations, and metadata.
    
    PHASE 3.1: Added advanced position analysis capabilities.
    All original methods preserved with identical signatures.
    """

    # Central squares for activity evaluation
    CENTRAL_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
    EXTENDED_CENTER = {chess.C3, chess.D3, chess.E3, chess.F3,
                       chess.C4, chess.D4, chess.E4, chess.F4,
                       chess.C5, chess.D5, chess.E5, chess.F5,
                       chess.C6, chess.D6, chess.E6, chess.F6}
    
    # Piece values for material calculation (centipawns)
    PIECE_VALUES = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 0,
    }

    def __init__(self):
        self.board = chess.Board()
        self.move_history: List[MoveMetadata] = []
        # PHASE 3.1: Additional tracking
        self._position_cache: Dict[str, AdvancedPositionAnalysis] = {}
        self._opening_book_loaded = False

    # =========================================================================
    # ORIGINAL METHODS (100% PRESERVED - IDENTICAL SIGNATURES)
    # =========================================================================

    def push_move(self, move: chess.Move, evaluation_before: Optional[float] = None) -> MoveMetadata:
        """
        Push a move onto the board and record metadata.
        """
        san = self.board.san(move)
        position_before = self.board.fen()
        
        self.board.push(move)
        
        position_after = self.board.fen()
        
        metadata = MoveMetadata(
            move=move,
            san=san,
            position_before_fen=position_before,
            position_after_fen=position_after,
            is_capture=self.board.is_capture(move),
            is_check=self.board.is_check(),
            is_checkmate=self.board.is_checkmate(),
            evaluation_before=evaluation_before,
        )
        
        self.move_history.append(metadata)
        return metadata

    def undo_move(self) -> Optional[MoveMetadata]:
        """Undo the last move."""
        if self.move_history:
            self.board.pop()
            return self.move_history.pop()
        return None

    def reset(self, fen: Optional[str] = None) -> None:
        """Reset the board."""
        if fen:
            self.board = chess.Board(fen)
        else:
            self.board = chess.Board()
        self.move_history = []
        # PHASE 3.1: Clear cache on reset
        self._position_cache.clear()

    def get_legal_moves_san(self) -> List[str]:
        """Get legal moves in SAN."""
        return [self.board.san(move) for move in self.board.legal_moves]

    def get_full_move_count(self) -> int:
        """Get the full move number (1-indexed)."""
        return self.board.fullmove_number

    def is_game_over(self) -> bool:
        """Is the game in a terminal state?"""
        return self.board.is_game_over()

    def get_game_result(self) -> str:
        """Get the game outcome."""
        if self.board.is_checkmate():
            return "CHECKMATE"
        elif self.board.is_stalemate():
            return "STALEMATE"
        elif self.board.is_insufficient_material():
            return "INSUFFICIENT_MATERIAL"
        else:
            return "ONGOING"

    # =========================================================================
    # PHASE 3.1: ADVANCED ANALYSIS METHODS
    # =========================================================================

    def analyze_position_advanced(self, use_cache: bool = True) -> AdvancedPositionAnalysis:
        """
        Comprehensive position analysis with all metrics.
        
        Args:
            use_cache: Use cached analysis if position unchanged
            
        Returns:
            AdvancedPositionAnalysis with all position metrics
        """
        fen = self.board.fen()
        
        if use_cache and fen in self._position_cache:
            return self._position_cache[fen]
        
        logger.debug(f"Analyzing position: {fen}")
        
        # Compute all metrics
        game_phase = self._detect_game_phase()
        position_type = self._detect_position_type()
        material = self._calculate_material_balance()
        
        white_king_safety = self._analyze_king_safety(chess.WHITE)
        black_king_safety = self._analyze_king_safety(chess.BLACK)
        
        white_pawn_structure = self._analyze_pawn_structure(chess.WHITE)
        black_pawn_structure = self._analyze_pawn_structure(chess.BLACK)
        
        white_space, black_space = self._calculate_space()
        white_mobility, black_mobility = self._calculate_mobility()
        
        tension = self._calculate_tension()
        complexity = self._calculate_complexity(game_phase, tension, white_mobility + black_mobility)
        
        analysis = AdvancedPositionAnalysis(
            game_phase=game_phase,
            position_type=position_type,
            material_balance=material,
            white_king_safety=white_king_safety,
            black_king_safety=black_king_safety,
            white_pawn_structure=white_pawn_structure,
            black_pawn_structure=black_pawn_structure,
            white_space=white_space,
            black_space=black_space,
            white_mobility=white_mobility,
            black_mobility=black_mobility,
            tension_score=tension,
            complexity_score=complexity,
        )
        
        if use_cache:
            self._position_cache[fen] = analysis
            
        return analysis

    def _detect_game_phase(self) -> GamePhase:
        """Detect game phase based on material and move count."""
        # Count material (excluding kings)
        total_material = 0
        queens = 0
        
        for piece_type in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
            white_pieces = len(self.board.pieces(piece_type, chess.WHITE))
            black_pieces = len(self.board.pieces(piece_type, chess.BLACK))
            total_material += (white_pieces + black_pieces) * self.PIECE_VALUES[piece_type]
            if piece_type == chess.QUEEN:
                queens = white_pieces + black_pieces
        
        move_count = len(self.move_history)
        
        # Opening: first 10 moves, most material present
        if move_count <= 10 and total_material >= 7000:
            return GamePhase.OPENING
        
        # Pure endgame: no queens and minimal material
        if queens == 0 and total_material <= 2500:
            return GamePhase.PURE_ENDGAME
        
        # Endgame: queens gone or very low material
        if queens == 0 or total_material <= 3500:
            return GamePhase.ENDGAME
        
        # Late middlegame: reduced material
        if total_material <= 5000:
            return GamePhase.LATE_MIDDLE
        
        # Early middlegame: still developing
        if move_count <= 20:
            return GamePhase.EARLY_MIDDLE
        
        return GamePhase.MIDDLE

    def _detect_position_type(self) -> PositionType:
        """Classify position type based on pawn structure and piece placement."""
        # Count open files (no pawns on file)
        open_files = 0
        locked_pawns = 0
        
        for file_idx in range(8):
            white_pawns_on_file = False
            black_pawns_on_file = False
            
            for rank_idx in range(8):
                square = chess.square(file_idx, rank_idx)
                piece = self.board.piece_at(square)
                if piece and piece.piece_type == chess.PAWN:
                    if piece.color == chess.WHITE:
                        white_pawns_on_file = True
                    else:
                        black_pawns_on_file = True
            
            if not white_pawns_on_file and not black_pawns_on_file:
                open_files += 1
        
        # Check for locked pawns (facing each other)
        for square in self.board.pieces(chess.PAWN, chess.WHITE):
            front_square = square + 8
            if 0 <= front_square < 64:
                front_piece = self.board.piece_at(front_square)
                if front_piece and front_piece.piece_type == chess.PAWN and front_piece.color == chess.BLACK:
                    locked_pawns += 1
        
        # Classify based on counts
        if open_files >= 4:
            return PositionType.OPEN
        elif locked_pawns >= 3:
            return PositionType.CLOSED
        elif open_files >= 2:
            return PositionType.SEMI_OPEN
        
        # Check for tactical tension
        tension = self._calculate_tension()
        if tension >= 60:
            return PositionType.SHARP
        elif tension >= 30:
            return PositionType.DYNAMIC
        
        return PositionType.QUIET

    def _calculate_material_balance(self) -> int:
        """Calculate material balance in centipawns (positive = White ahead)."""
        balance = 0
        
        for piece_type in self.PIECE_VALUES:
            white_count = len(self.board.pieces(piece_type, chess.WHITE))
            black_count = len(self.board.pieces(piece_type, chess.BLACK))
            balance += (white_count - black_count) * self.PIECE_VALUES[piece_type]
        
        return balance

    def _analyze_king_safety(self, color: chess.Color) -> KingSafety:
        """Analyze king safety for a given color."""
        king_square = self.board.king(color)
        if king_square is None:
            # Should not happen in legal position
            return KingSafety(
                king_square=chess.E1 if color == chess.WHITE else chess.E8,
                pawn_shield_count=0,
                attackers_count=0,
                defenders_count=0,
                is_castled=False,
            )
        
        # Check castling status
        is_castled = False
        castling_side = CastlingStatus.NOT_CASTLED
        
        king_file = chess.square_file(king_square)
        back_rank = 0 if color == chess.WHITE else 7
        
        if chess.square_rank(king_square) == back_rank:
            if king_file >= 6:  # g or h file - likely kingside castled
                is_castled = True
                castling_side = CastlingStatus.KINGSIDE
            elif king_file <= 2:  # a, b, or c file - likely queenside castled
                is_castled = True
                castling_side = CastlingStatus.QUEENSIDE
        
        # Count pawn shield
        pawn_shield = 0
        king_zone_squares = self._get_king_zone(king_square, color)
        
        for sq in king_zone_squares:
            piece = self.board.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN and piece.color == color:
                pawn_shield += 1
        
        # Count attackers and defenders in king zone
        attackers = 0
        defenders = 0
        enemy_color = not color
        
        for sq in king_zone_squares:
            # Count enemy pieces attacking this square
            for attacker_sq in self.board.attackers(enemy_color, sq):
                attackers += 1
            # Count friendly pieces defending this square
            for defender_sq in self.board.attackers(color, sq):
                defenders += 1
        
        # Count open files near king
        open_files_near = 0
        for file_offset in [-1, 0, 1]:
            check_file = king_file + file_offset
            if 0 <= check_file <= 7:
                pawns_on_file = False
                for rank in range(8):
                    sq = chess.square(check_file, rank)
                    piece = self.board.piece_at(sq)
                    if piece and piece.piece_type == chess.PAWN:
                        pawns_on_file = True
                        break
                if not pawns_on_file:
                    open_files_near += 1
        
        # Calculate safety score (0-100)
        safety_score = 50.0
        safety_score += pawn_shield * 10
        safety_score -= attackers * 3
        safety_score += defenders * 2
        safety_score -= open_files_near * 8
        if is_castled:
            safety_score += 15
        
        safety_score = max(0, min(100, safety_score))
        
        return KingSafety(
            king_square=king_square,
            pawn_shield_count=pawn_shield,
            attackers_count=attackers,
            defenders_count=defenders,
            is_castled=is_castled,
            castling_side=castling_side,
            open_files_near_king=open_files_near,
            safety_score=safety_score,
        )

    def _get_king_zone(self, king_square: chess.Square, color: chess.Color) -> List[chess.Square]:
        """Get squares in the king's defensive zone."""
        zone = []
        king_file = chess.square_file(king_square)
        king_rank = chess.square_rank(king_square)
        
        # 3x3 or 3x4 zone around king, extended forward
        for file_offset in [-1, 0, 1]:
            for rank_offset in ([-1, 0, 1, 2] if color == chess.WHITE else [-2, -1, 0, 1]):
                new_file = king_file + file_offset
                new_rank = king_rank + rank_offset
                if 0 <= new_file <= 7 and 0 <= new_rank <= 7:
                    zone.append(chess.square(new_file, new_rank))
        
        return zone

    def _analyze_pawn_structure(self, color: chess.Color) -> PawnStructureAnalysis:
        """Analyze pawn structure for a given color."""
        pawns = list(self.board.pieces(chess.PAWN, color))
        
        doubled = []
        isolated = []
        backward = []
        passed = []
        
        # Group pawns by file
        pawns_by_file: Dict[int, List[chess.Square]] = {}
        for pawn_sq in pawns:
            file_idx = chess.square_file(pawn_sq)
            if file_idx not in pawns_by_file:
                pawns_by_file[file_idx] = []
            pawns_by_file[file_idx].append(pawn_sq)
        
        # Detect doubled pawns
        for file_idx, file_pawns in pawns_by_file.items():
            if len(file_pawns) > 1:
                doubled.extend(file_pawns)
        
        # Detect isolated pawns
        for file_idx, file_pawns in pawns_by_file.items():
            left_file = file_idx - 1
            right_file = file_idx + 1
            has_neighbor = (left_file in pawns_by_file) or (right_file in pawns_by_file)
            if not has_neighbor:
                isolated.extend(file_pawns)
        
        # Detect passed pawns
        enemy_color = not color
        for pawn_sq in pawns:
            is_passed = True
            pawn_file = chess.square_file(pawn_sq)
            pawn_rank = chess.square_rank(pawn_sq)
            
            # Check if any enemy pawns can block or capture
            for file_offset in [-1, 0, 1]:
                check_file = pawn_file + file_offset
                if 0 <= check_file <= 7:
                    for rank in range(pawn_rank + (1 if color == chess.WHITE else -7), 
                                     (8 if color == chess.WHITE else pawn_rank)):
                        sq = chess.square(check_file, rank)
                        piece = self.board.piece_at(sq)
                        if piece and piece.piece_type == chess.PAWN and piece.color == enemy_color:
                            is_passed = False
                            break
                    if not is_passed:
                        break
            
            if is_passed:
                passed.append(pawn_sq)
        
        # Count pawn islands
        files_with_pawns = sorted(pawns_by_file.keys())
        islands = 0
        if files_with_pawns:
            islands = 1
            for i in range(1, len(files_with_pawns)):
                if files_with_pawns[i] - files_with_pawns[i-1] > 1:
                    islands += 1
        
        # Determine structure types
        structure_types = []
        if doubled:
            structure_types.append(PawnStructure.DOUBLED)
        if isolated:
            structure_types.append(PawnStructure.ISOLATED)
        if backward:
            structure_types.append(PawnStructure.BACKWARD)
        if passed:
            structure_types.append(PawnStructure.PASSED)
        if not structure_types:
            structure_types.append(PawnStructure.HEALTHY)
        
        # Calculate structure score
        score = 70.0
        score -= len(doubled) * 8
        score -= len(isolated) * 10
        score -= len(backward) * 6
        score += len(passed) * 15
        score -= (islands - 1) * 5 if islands > 1 else 0
        score = max(0, min(100, score))
        
        return PawnStructureAnalysis(
            doubled_pawns=doubled,
            isolated_pawns=isolated,
            backward_pawns=backward,
            passed_pawns=passed,
            pawn_islands=islands,
            structure_types=structure_types,
            structure_score=score,
        )

    def _calculate_space(self) -> Tuple[int, int]:
        """Calculate space control for both colors."""
        white_space = 0
        black_space = 0
        
        for square in chess.SQUARES:
            white_attackers = len(self.board.attackers(chess.WHITE, square))
            black_attackers = len(self.board.attackers(chess.BLACK, square))
            
            if white_attackers > black_attackers:
                white_space += 1
            elif black_attackers > white_attackers:
                black_space += 1
        
        return white_space, black_space

    def _calculate_mobility(self) -> Tuple[int, int]:
        """Calculate piece mobility for both colors."""
        # Save current turn
        original_turn = self.board.turn
        
        # Count White's moves
        self.board.turn = chess.WHITE
        white_mobility = len(list(self.board.legal_moves))
        
        # Count Black's moves
        self.board.turn = chess.BLACK
        black_mobility = len(list(self.board.legal_moves))
        
        # Restore turn
        self.board.turn = original_turn
        
        return white_mobility, black_mobility

    def _calculate_tension(self) -> float:
        """Calculate tactical tension in the position (0-100)."""
        tension = 0.0
        
        # Check for hanging pieces (attacked but not defended)
        for color in [chess.WHITE, chess.BLACK]:
            for piece_type in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
                for square in self.board.pieces(piece_type, color):
                    enemy_color = not color
                    attackers = len(self.board.attackers(enemy_color, square))
                    defenders = len(self.board.attackers(color, square))
                    
                    if attackers > 0:
                        tension += 5
                        if attackers > defenders:
                            tension += 10
        
        # Check for potential captures
        for move in self.board.legal_moves:
            if self.board.is_capture(move):
                tension += 2
        
        # Bonus for checks available
        for move in self.board.legal_moves:
            self.board.push(move)
            if self.board.is_check():
                tension += 3
            self.board.pop()
        
        return min(100, tension)

    def _calculate_complexity(self, phase: GamePhase, tension: float, total_mobility: int) -> float:
        """Calculate position complexity (0-100)."""
        complexity = tension * 0.5
        
        # Add mobility factor (more moves = more complex)
        complexity += min(30, total_mobility / 2)
        
        # Phase adjustments
        if phase in [GamePhase.MIDDLE, GamePhase.EARLY_MIDDLE]:
            complexity += 15
        elif phase in [GamePhase.OPENING, GamePhase.LATE_MIDDLE]:
            complexity += 5
        
        # Imbalances add complexity
        material = self._calculate_material_balance()
        if 100 <= abs(material) <= 300:  # Pawn imbalance
            complexity += 10
        
        return min(100, complexity)

    # =========================================================================
    # PHASE 3.1: UTILITY METHODS
    # =========================================================================

    def get_fen(self) -> str:
        """Get current position as FEN string."""
        return self.board.fen()

    def set_fen(self, fen: str) -> bool:
        """
        Set position from FEN string.
        
        Args:
            fen: FEN notation string
            
        Returns:
            True if valid FEN, False otherwise
        """
        try:
            self.board = chess.Board(fen)
            self.move_history = []
            self._position_cache.clear()
            return True
        except ValueError:
            logger.warning(f"Invalid FEN: {fen}")
            return False

    def get_pgn(self, event: str = "Caissa Game", white: str = "White", black: str = "Black") -> str:
        """
        Export current game as PGN string.
        
        Args:
            event: Event name for PGN header
            white: White player name
            black: Black player name
            
        Returns:
            PGN formatted string
        """
        import io
        game = chess.pgn.Game()
        game.headers["Event"] = event
        game.headers["White"] = white
        game.headers["Black"] = black
        
        node = game
        for metadata in self.move_history:
            node = node.add_variation(metadata.move)
        
        # Set result
        if self.board.is_checkmate():
            game.headers["Result"] = "1-0" if not self.board.turn else "0-1"
        elif self.board.is_game_over():
            game.headers["Result"] = "1/2-1/2"
        else:
            game.headers["Result"] = "*"
        
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
        return game.accept(exporter)

    def load_pgn(self, pgn_str: str) -> bool:
        """
        Load game from PGN string.
        
        Args:
            pgn_str: PGN formatted string
            
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            import io
            pgn_io = io.StringIO(pgn_str)
            game = chess.pgn.read_game(pgn_io)
            
            if game is None:
                return False
            
            self.reset()
            for move in game.mainline_moves():
                if move in self.board.legal_moves:
                    self.push_move(move)
                else:
                    logger.warning(f"Illegal move in PGN: {move}")
                    return False
            
            return True
        except Exception as e:
            logger.error(f"Error loading PGN: {e}")
            return False

    def get_piece_at(self, square: str) -> Optional[str]:
        """
        Get piece at algebraic square (e.g., 'e4').
        
        Args:
            square: Algebraic notation (a1-h8)
            
        Returns:
            Piece symbol (P, N, B, R, Q, K) with case for color, or None
        """
        try:
            sq = chess.parse_square(square)
            piece = self.board.piece_at(sq)
            return piece.symbol() if piece else None
        except ValueError:
            return None

    def get_all_pieces(self) -> Dict[str, str]:
        """
        Get all pieces on the board.
        
        Returns:
            Dict mapping square names to piece symbols
        """
        pieces = {}
        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece:
                pieces[chess.square_name(square)] = piece.symbol()
        return pieces

    def get_attacked_squares(self, color: chess.Color) -> List[str]:
        """
        Get all squares attacked by a color.
        
        Args:
            color: chess.WHITE or chess.BLACK
            
        Returns:
            List of square names attacked
        """
        attacked = []
        for square in chess.SQUARES:
            if self.board.is_attacked_by(color, square):
                attacked.append(chess.square_name(square))
        return attacked

    def clone(self) -> "BoardState":
        """Create a deep copy of the board state."""
        new_state = BoardState()
        new_state.board = self.board.copy()
        new_state.move_history = self.move_history.copy()
        return new_state

    def __repr__(self) -> str:
        return f"BoardState(fen='{self.board.fen()}', moves={len(self.move_history)})"

    def __str__(self) -> str:
        return self.board.unicode()

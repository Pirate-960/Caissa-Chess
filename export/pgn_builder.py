"""
export/pgn_builder.py

Constructs professional-grade PGN (Portable Game Notation) output.
"""

from typing import List, Dict, Optional
from datetime import datetime
import chess


class PGNBuilder:
    """
    Builds PGN files from game data.
    """

    def __init__(
        self,
        event: str = "Caissa AI Generation",
        white: str = "Caissa White",
        black: str = "Caissa Black",
        site: str = "The Aesthetic Engine",
    ):
        self.event = event
        self.white = white
        self.black = black
        self.site = site
        self.date = datetime.now().strftime("%Y.%m.%d")
        self.moves: List[str] = []
        self.annotations: Dict[int, str] = {}  # {move_number: annotation}

    def add_move(self, move: str, annotation: Optional[str] = None) -> None:
        """Add a move to the game."""
        self.moves.append(move)
        if annotation:
            self.annotations[len(self.moves) - 1] = annotation

    def add_moves_batch(self, moves: List[str]) -> None:
        """Add multiple moves at once."""
        self.moves.extend(moves)

    def build_pgn(self, result: str = "1-0") -> str:
        """
        Build the complete PGN.
        
        Args:
            result: Game result ("1-0", "0-1", "1/2-1/2")
        
        Returns:
            Complete PGN string
        """
        pgn = ""
        
        # Headers
        pgn += f'[Event "{self.event}"]\n'
        pgn += f'[Site "{self.site}"]\n'
        pgn += f'[Date "{self.date}"]\n'
        pgn += f'[White "{self.white}"]\n'
        pgn += f'[Black "{self.black}"]\n'
        pgn += f'[Result "{result}"]\n'
        pgn += "\n"
        
        # Moves
        move_text = ""
        for i, move in enumerate(self.moves):
            move_num = i // 2 + 1
            
            if i % 2 == 0:
                # White's move
                move_text += f"{move_num}. {move}"
            else:
                # Black's move
                move_text += f" {move}"
                if (i + 1) % 4 == 0:  # Line break every 2 full moves
                    move_text += "\n"
                else:
                    move_text += " "
            
            # Add annotation if present
            if i in self.annotations:
                move_text += f" {self.annotations[i]}"
        
        pgn += move_text.rstrip() + f" {result}\n"
        
        return pgn

    def save_to_file(self, filename: str, result: str = "1-0") -> bool:
        """Save the PGN to a file."""
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(self.build_pgn(result))
            return True
        except Exception as e:
            print(f"Error saving PGN: {str(e)}")
            return False


# Example usage
if __name__ == "__main__":
    builder = PGNBuilder(
        event="Scholar's Mate Example",
        white="White Player",
        black="Black Player",
    )
    
    moves = [
        "e4", "e5",
        "Bc4", "Nc6",
        "Qh5", "Nf6",
        "Qxf7",
    ]
    
    builder.add_moves_batch(moves)
    builder.annotations[0] = "!!"  # Brilliant first move
    
    pgn = builder.build_pgn(result="1-0")
    print(pgn)

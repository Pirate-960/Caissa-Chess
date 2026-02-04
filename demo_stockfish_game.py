#!/usr/bin/env python3
"""
Demo: Generate a chess game using Stockfish best moves.

This demonstrates that Stockfish is working and can generate high-quality games
without requiring an LLM.
"""

import os
from pathlib import Path
from engine.stockfish_client import StockfishClient
import chess

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Get Stockfish path from environment or use default
STOCKFISH_PATH = os.environ.get(
    "STOCKFISH_PATH",
    str(Path(__file__).parent / "engines" / "stockfish-windows-x86-64-avx2.exe")
)


def generate_stockfish_game(num_moves: int = 20) -> str:
    """
    Generate a game by having Stockfish play both sides.
    
    Args:
        num_moves: Number of half-moves (plies) to generate
        
    Returns:
        PGN string of the game
    """
    print(f"📂 Using Stockfish: {STOCKFISH_PATH}")
    client = StockfishClient(binary_path=STOCKFISH_PATH)
    board = chess.Board()
    moves = []
    
    print(f"🔧 Stockfish Mode: {client.mode}")
    print(f"♟️  Generating {num_moves} half-moves...\n")
    
    for i in range(num_moves):
        if board.is_game_over():
            print(f"\n🏁 Game over: {board.result()}")
            break
            
        result = client.evaluate(board)
        
        if result.best_move:
            san = board.san(result.best_move)
            moves.append(san)
            
            # Format output
            move_num = (i // 2) + 1
            if i % 2 == 0:
                print(f"{move_num}. {san}", end="")
            else:
                print(f" {san}")
            
            board.push(result.best_move)
    
    # Print final position
    print("\n")
    print("=" * 40)
    print("Final Position:")
    print(board)
    print("=" * 40)
    
    # Final evaluation
    final_eval = client.evaluate(board)
    print(f"\n📊 Final Evaluation: {final_eval.score_cp} centipawns")
    print(f"🎯 Best continuation: {final_eval.best_move}")
    
    # Build PGN
    pgn = " ".join(
        f"{(i//2)+1}. {moves[i]}" if i % 2 == 0 else moves[i]
        for i in range(len(moves))
    )
    
    print(f"\n📝 PGN:\n{pgn}")
    
    # Cleanup engine
    client.close()
    
    return pgn


if __name__ == "__main__":
    generate_stockfish_game(20)

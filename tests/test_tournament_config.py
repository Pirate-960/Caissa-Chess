"""Quick test to verify tournament config loads correctly."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from config_manager import cfg
    
    print("=" * 60)
    print("TOURNAMENT CONFIGURATION TEST")
    print("=" * 60)
    
    # Test that tournament config exists
    assert hasattr(cfg, 'tournament'), "❌ Tournament config not found!"
    print("✓ Tournament config exists")
    
    # Test basic fields
    print(f"✓ Default format: {cfg.tournament.default_format}")
    print(f"✓ Default time control: {cfg.tournament.default_time_control}")
    print(f"✓ Default rounds: {cfg.tournament.default_rounds}")
    
    # Test nested configs
    print(f"✓ ELO initial rating: {cfg.tournament.elo.initial_rating}")
    print(f"✓ Match max moves: {cfg.tournament.match.max_moves}")
    print(f"✓ Commentary enabled: {cfg.tournament.commentary.enabled}")
    print(f"✓ Output directory: {cfg.tournament.output.output_dir}")
    
    # Test time per move dict
    print(f"✓ Rapid time per move: {cfg.tournament.time_per_move['rapid']}s")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - Tournament config loaded successfully!")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

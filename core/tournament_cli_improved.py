"""
core/tournament_cli_improved.py

Improved CLI workflows for LLM vs LLM matches and tournaments.

Features:
- Smart bulk player input ("gemini x 100", "all", ranges)
- Go back navigation at every step
- Quick selection shortcuts
- Better step ordering
- Parallel match execution support

Author: CAISSA Team
Version: 0.5.0
"""

import re
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════════════════════════
# SMART PLAYER SELECTION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PlayerSelectionResult:
    """Result of player selection parsing."""
    providers: List[str]
    go_back: bool = False
    error: Optional[str] = None


def parse_smart_player_input(user_input: str, available_providers: List[str]) -> PlayerSelectionResult:
    """
    Parse smart player selection input with multiple formats:
    
    Supported formats:
    1. Comma-separated indices: "1,2,3,4,5"
    2. Ranges: "1-5" or "1..5" (inclusive)
    3. Bulk same provider: "gemini x 100" or "100 x gemini" or "gemini*100"
    4. Mixed: "gemini x 50, claude x 30, gpt4 x 20"
    5. All providers: "all" or "*"
    6. Provider name directly: "gemini, claude, gpt4"
    7. Combinations: "1-3, gemini x 10, all"
    8. Back navigation: "back", "b", "0"
    
    Examples:
        "gemini x 100" → 100 gemini players
        "1,2,3,4,5" → Players 1,2,3,4,5
        "1-5" → Players 1 through 5
        "gemini x 50, claude x 50" → 50 gemini + 50 claude
        "all" → All available providers (1 each)
        "all x 10" → All available providers (10 each)
        "back" → Go back to previous menu
    
    Args:
        user_input: Raw input from user
        available_providers: List of provider names
    
    Returns:
        PlayerSelectionResult with parsed providers or error
    """
    user_input = user_input.strip().lower()
    
    # Check for back navigation
    if user_input in ["back", "b", "0", "<"]:
        return PlayerSelectionResult(providers=[], go_back=True)
    
    if not user_input:
        return PlayerSelectionResult(providers=[], error="Empty input")
    
    result_providers = []
    
    # Handle "all" special case
    if user_input in ["all", "*"]:
        return PlayerSelectionResult(providers=available_providers.copy())
    
    # Handle "all x N" pattern
    all_match = re.match(r'^all\s*x\s*(\d+)$', user_input)
    if all_match:
        count = int(all_match.group(1))
        return PlayerSelectionResult(providers=available_providers * count)
    
    # Split by comma for multiple selections
    parts = [p.strip() for p in user_input.split(',')]
    
    for part in parts:
        if not part:
            continue
        
        # Pattern 1: Bulk format "provider x count" or "count x provider"
        bulk_match = re.match(r'^(\w+)\s*[x*]\s*(\d+)$', part)
        if bulk_match:
            provider_name, count_str = bulk_match.groups()
            count = int(count_str)
            
            # Find matching provider (case-insensitive)
            matched = _find_provider(provider_name, available_providers)
            if matched:
                result_providers.extend([matched] * count)
            else:
                return PlayerSelectionResult(
                    providers=[], 
                    error=f"Provider '{provider_name}' not found"
                )
            continue
        
        # Pattern 2: Reverse bulk "count x provider"
        reverse_bulk_match = re.match(r'^(\d+)\s*[x*]\s*(\w+)$', part)
        if reverse_bulk_match:
            count_str, provider_name = reverse_bulk_match.groups()
            count = int(count_str)
            
            matched = _find_provider(provider_name, available_providers)
            if matched:
                result_providers.extend([matched] * count)
            else:
                return PlayerSelectionResult(
                    providers=[], 
                    error=f"Provider '{provider_name}' not found"
                )
            continue
        
        # Pattern 3: Range "1-5" or "1..5"
        range_match = re.match(r'^(\d+)\s*[-\.]{1,2}\s*(\d+)$', part)
        if range_match:
            start, end = map(int, range_match.groups())
            if start < 1 or end > len(available_providers):
                return PlayerSelectionResult(
                    providers=[], 
                    error=f"Range {start}-{end} out of bounds (1-{len(available_providers)})"
                )
            if start > end:
                start, end = end, start  # Swap if reversed
            
            for idx in range(start, end + 1):
                result_providers.append(available_providers[idx - 1])
            continue
        
        # Pattern 4: Single number index
        if part.isdigit():
            idx = int(part)
            if 1 <= idx <= len(available_providers):
                result_providers.append(available_providers[idx - 1])
            else:
                return PlayerSelectionResult(
                    providers=[], 
                    error=f"Index {idx} out of range (1-{len(available_providers)})"
                )
            continue
        
        # Pattern 5: Provider name directly
        matched = _find_provider(part, available_providers)
        if matched:
            result_providers.append(matched)
        else:
            return PlayerSelectionResult(
                providers=[], 
                error=f"Invalid input: '{part}'"
            )
    
    if not result_providers:
        return PlayerSelectionResult(providers=[], error="No players selected")
    
    return PlayerSelectionResult(providers=result_providers)


def _find_provider(name: str, available: List[str]) -> Optional[str]:
    """Find provider by name (case-insensitive prefix match)."""
    name_lower = name.lower()
    
    # Exact match first
    for prov in available:
        if prov.lower() == name_lower:
            return prov
    
    # Prefix match
    for prov in available:
        if prov.lower().startswith(name_lower):
            return prov
    
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# STEP-BY-STEP BUILDERS WITH NAVIGATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MatchConfig:
    """Configuration for a single LLM vs LLM match."""
    white_provider: str
    black_provider: str
    time_control: str
    export_format: str
    enable_analysis: bool = True
    enable_commentary: bool = True
    output_dir: str = "games/matches/"


@dataclass
class TournamentConfig:
    """Configuration for an LLM tournament."""
    name: str
    format: str
    providers: List[str]
    time_control: str
    export_format: str
    enable_analysis: bool = True
    enable_commentary: bool = True  # Added commentary flag
    enable_parallel: bool = True  # NEW: Parallel match execution
    max_workers: int = 4  # NEW: Thread pool size
    output_dir: str = "tournaments/"


class WorkflowStep:
    """Base class for workflow steps with go-back support."""
    
    def __init__(self, title: str, allow_back: bool = True):
        self.title = title
        self.allow_back = allow_back
    
    def execute(self) -> Tuple[any, bool]:
        """
        Execute the step.
        
        Returns:
            (result, go_back) tuple
            - result: Step-specific result
            - go_back: True if user wants to go back
        """
        raise NotImplementedError


# ═══════════════════════════════════════════════════════════════════════════════
# MATCH BUILDER WITH IMPROVED FLOW
# ═══════════════════════════════════════════════════════════════════════════════

class ImprovedMatchBuilder:
    """
    Improved LLM vs LLM match builder with smart navigation.
    
    New flow order (optimized):
    1. Time control (sets context for entire match)
    2. White player selection
    3. Black player selection
    4. Analysis options (post-match analysis, commentary)
    5. Export format
    6. Confirm and execute
    
    Features:
    - Go back at any step
    - Quick shortcuts (same provider for both, random selection)
    - Smart defaults based on previous selections
    """
    
    def __init__(self, available_providers: List[str]):
        self.providers = available_providers
        self.config = MatchConfig(
            white_provider="",
            black_provider="",
            time_control="rapid",
            export_format="html",
        )
    
    def build(self) -> Optional[MatchConfig]:
        """
        Interactive match configuration builder.
        
        Returns:
            MatchConfig if successful, None if cancelled/back
        """
        steps = [
            ("time_control", self._select_time_control),
            ("white_player", self._select_white_player),
            ("black_player", self._select_black_player),
            ("analysis", self._configure_analysis),
            ("export", self._select_export_format),
            ("confirm", self._confirm_match),
        ]
        
        current_step = 0
        
        while current_step < len(steps):
            step_name, step_func = steps[current_step]
            
            result, go_back = step_func()
            
            if go_back:
                if current_step == 0:
                    # At first step, go back means cancel
                    return None
                else:
                    # Go to previous step
                    current_step -= 1
                    continue
            
            # Move to next step
            current_step += 1
        
        return self.config
    
    def _select_time_control(self) -> Tuple[str, bool]:
        """Step 1: Select time control."""
        print("\n" + "="*60)
        print("  ⏱️  STEP 1: Time Control")
        print("="*60)
        
        time_controls = {
            1: ("bullet", "Bullet (5s)", "⚡ Lightning-fast games"),
            2: ("blitz", "Blitz (15s)", "💨 Quick tactical battles"),
            3: ("rapid", "Rapid (30s)", "⏰ Balanced pace (recommended)"),
            4: ("classical", "Classical (60s)", "♟️ Deep strategic games"),
            5: ("unlimited", "Unlimited", "∞ No time pressure"),
        }
        
        print("\n  Options:")
        for num, (key, name, desc) in time_controls.items():
            default_marker = " [DEFAULT]" if key == "rapid" else ""
            print(f"    {num}. {name:20} - {desc}{default_marker}")
        print("    0. ← Back")
        
        choice = self._prompt_with_back("Select time control", default=3, min_val=1, max_val=5)
        
        if choice == 0:
            return None, True
        
        self.config.time_control = time_controls[choice][0]
        return self.config.time_control, False
    
    def _select_white_player(self) -> Tuple[str, bool]:
        """Step 2: Select white player."""
        print("\n" + "="*60)
        print("  ⚪ STEP 2: White Player")
        print("="*60)
        
        print("\n  Available providers:")
        for i, prov in enumerate(self.providers, 1):
            print(f"    {i}. {prov}")
        print("    0. ← Back")
        
        choice = self._prompt_with_back("Select WHITE player", default=1, min_val=1, max_val=len(self.providers))
        
        if choice == 0:
            return None, True
        
        self.config.white_provider = self.providers[choice - 1]
        return self.config.white_provider, False
    
    def _select_black_player(self) -> Tuple[str, bool]:
        """Step 3: Select black player."""
        print("\n" + "="*60)
        print(f"  ⚫ STEP 3: Black Player (White: {self.config.white_provider})")
        print("="*60)
        
        print("\n  Options:")
        print(f"    S. Same as White ({self.config.white_provider})")
        print("\n  Or select different provider:")
        for i, prov in enumerate(self.providers, 1):
            marker = " [SAME AS WHITE]" if prov == self.config.white_provider else ""
            print(f"    {i}. {prov}{marker}")
        print("    0. ← Back")
        
        choice_str = input(f"\n  > Select BLACK player [S]: ").strip().upper()
        
        if choice_str in ["0", "BACK", "B"]:
            return None, True
        
        if choice_str in ["S", ""]:
            # Same as white
            self.config.black_provider = self.config.white_provider
        else:
            try:
                choice = int(choice_str)
                if 1 <= choice <= len(self.providers):
                    self.config.black_provider = self.providers[choice - 1]
                else:
                    print("  Invalid choice. Using same as White.")
                    self.config.black_provider = self.config.white_provider
            except ValueError:
                print("  Invalid input. Using same as White.")
                self.config.black_provider = self.config.white_provider
        
        return self.config.black_provider, False
    
    def _configure_analysis(self) -> Tuple[Dict, bool]:
        """Step 4: Configure post-match analysis."""
        print("\n" + "="*60)
        print("  ✨ STEP 4: Post-Match Analysis")
        print("="*60)
        
        print("\n  Post-match analysis enriches games with:")
        print("    • Beauty scores and critical moments")
        print("    • Stockfish evaluations and accuracy metrics")
        print("    • Strategic commentary (optional)")
        print()
        
        print("  Options:")
        print("    1. Full Analysis + Commentary [RECOMMENDED]")
        print("    2. Analysis Only (no commentary)")
        print("    3. Skip Analysis (raw moves only)")
        print("    0. ← Back")
        
        choice = self._prompt_with_back("Select analysis level", default=1, min_val=1, max_val=3)
        
        if choice == 0:
            return None, True
        
        if choice == 1:
            self.config.enable_analysis = True
            self.config.enable_commentary = True
        elif choice == 2:
            self.config.enable_analysis = True
            self.config.enable_commentary = False
        else:
            self.config.enable_analysis = False
            self.config.enable_commentary = False
        
        return {"analysis": self.config.enable_analysis, "commentary": self.config.enable_commentary}, False
    
    def _select_export_format(self) -> Tuple[str, bool]:
        """Step 5: Select export format."""
        print("\n" + "="*60)
        print("  📁 STEP 5: Export Format")
        print("="*60)
        
        formats = {
            1: ("html", "HTML", "🌐 Rich interactive dashboard [RECOMMENDED]"),
            2: ("pgn", "PGN", "♟️ Standard chess notation"),
            3: ("json", "JSON", "📊 Structured data format"),
            4: ("markdown", "Markdown", "📝 Readable text format"),
            5: ("all", "ALL", "✨ Export in all formats"),
        }
        
        print("\n  Options:")
        for num, (key, name, desc) in formats.items():
            print(f"    {num}. {name:12} - {desc}")
        print("    0. ← Back")
        
        choice = self._prompt_with_back("Select export format", default=1, min_val=1, max_val=5)
        
        if choice == 0:
            return None, True
        
        self.config.export_format = formats[choice][0]
        return self.config.export_format, False
    
    def _confirm_match(self) -> Tuple[bool, bool]:
        """Step 6: Confirm and execute."""
        print("\n" + "="*60)
        print("  ✅ MATCH CONFIGURATION")
        print("="*60)
        
        print(f"\n  ⚪ White:         {self.config.white_provider}")
        print(f"  ⚫ Black:         {self.config.black_provider}")
        print(f"  ⏱️  Time Control:  {self.config.time_control}")
        
        analysis_status = "Full Analysis + Commentary" if self.config.enable_commentary else \
                         "Analysis Only" if self.config.enable_analysis else \
                         "No Analysis"
        print(f"  ✨ Analysis:      {analysis_status}")
        
        print(f"  📁 Export:        {self.config.export_format}")
        print(f"  📂 Output:        {self.config.output_dir}")
        print()
        
        choice_str = input(f"  > Start match? [Y/n/back]: ").strip().lower()
        
        if choice_str in ["back", "b"]:
            return False, True
        
        if choice_str in ["n", "no"]:
            return False, False  # Cancel entirely
        
        return True, False  # Confirmed
    
    def _prompt_with_back(self, prompt: str, default: int, min_val: int, max_val: int) -> int:
        """Prompt for integer with validation and back support."""
        while True:
            user_input = input(f"\n  > {prompt} [{default}]: ").strip()
            
            if not user_input:
                return default
            
            if user_input.lower() in ["back", "b", "0"]:
                return 0
            
            try:
                value = int(user_input)
                if min_val <= value <= max_val:
                    return value
                else:
                    print(f"  ⚠️  Please enter a number between {min_val} and {max_val}")
            except ValueError:
                print(f"  ⚠️  Invalid input. Please enter a number.")


# ═══════════════════════════════════════════════════════════════════════════════
# TOURNAMENT BUILDER WITH SMART PLAYER INPUT
# ═══════════════════════════════════════════════════════════════════════════════

class ImprovedTournamentBuilder:
    """
    Improved tournament builder with smart bulk player selection.
    
    New features:
    - Smart player input ("gemini x 100", ranges, "all")
    - Parallel execution option
    - Better step ordering
    - Go back navigation
    """
    
    def __init__(self, available_providers: List[str]):
        self.providers = available_providers
        self.config = TournamentConfig(
            name="",
            format="round_robin",
            providers=[],
            time_control="rapid",
            export_format="html",
        )
    
    def build(self) -> Optional[TournamentConfig]:
        """
        Interactive tournament configuration builder.
        
        Returns:
            TournamentConfig if successful, None if cancelled
        """
        steps = [
            ("format", self._select_format),
            ("time_control", self._select_time_control),
            ("players", self._select_players),
            ("analysis", self._configure_analysis),
            ("parallel", self._configure_parallel),
            ("export", self._select_export_format),
            ("name", self._set_tournament_name),
            ("confirm", self._confirm_tournament),
        ]
        
        current_step = 0
        
        while current_step < len(steps):
            step_name, step_func = steps[current_step]
            
            result, go_back = step_func()
            
            if go_back:
                if current_step == 0:
                    return None
                else:
                    current_step -= 1
                    continue
            
            current_step += 1
        
        return self.config
    
    def _select_format(self) -> Tuple[str, bool]:
        """Step 1: Select tournament format."""
        print("\n" + "="*60)
        print("  🏆 STEP 1: Tournament Format")
        print("="*60)
        
        formats = {
            1: ("round_robin", "Round Robin", "Everyone plays everyone once"),
            2: ("double_round_robin", "Double Round Robin", "Everyone plays everyone twice (with color swap)"),
            3: ("swiss", "Swiss System", "Pair by score each round (fair & fast)"),
            4: ("knockout", "Knockout", "Single elimination bracket"),
        }
        
        print("\n  Options:")
        for num, (key, name, desc) in formats.items():
            default_marker = " [DEFAULT]" if key == "round_robin" else ""
            print(f"    {num}. {name:22} - {desc}{default_marker}")
        print("    0. ← Back")
        
        choice = self._prompt_with_back("Select format", default=1, min_val=1, max_val=4)
        
        if choice == 0:
            return None, True
        
        self.config.format = formats[choice][0]
        return self.config.format, False
    
    def _select_time_control(self) -> Tuple[str, bool]:
        """Step 2: Select time control (same as match)."""
        print("\n" + "="*60)
        print("  ⏱️  STEP 2: Time Control")
        print("="*60)
        
        time_controls = {
            1: ("bullet", "Bullet (5s)"),
            2: ("blitz", "Blitz (15s)"),
            3: ("rapid", "Rapid (30s) [RECOMMENDED]"),
            4: ("classical", "Classical (60s)"),
            5: ("unlimited", "Unlimited"),
        }
        
        print("\n  Options:")
        for num, (key, name) in time_controls.items():
            print(f"    {num}. {name}")
        print("    0. ← Back")
        
        choice = self._prompt_with_back("Select time control", default=3, min_val=1, max_val=5)
        
        if choice == 0:
            return None, True
        
        self.config.time_control = time_controls[choice][0]
        return self.config.time_control, False
    
    def _select_players(self) -> Tuple[List[str], bool]:
        """Step 3: Select players with smart input."""
        print("\n" + "="*60)
        print(f"  👥 STEP 3: Select Players")
        print("="*60)
        
        print("\n  Available providers:")
        for i, prov in enumerate(self.providers, 1):
            print(f"    {i}. {prov}")
        
        print("\n  📖 Smart Selection Help:")
        print("     • Bulk same:       gemini x 100  or  100 x gemini")
        print("     • Range:           1-5  or  1..5")
        print("     • Mix providers:   gemini x 50, claude x 30, gpt4 x 20")
        print("     • All providers:   all  or  all x 10")
        print("     • Comma list:      1,2,3,4,5")
        print("     • Direct names:    gemini, claude, gpt4")
        print()
        print("  Examples:")
        print("     • gemini x 100     → 100 gemini players")
        print("     • 1-3, 5           → Players 1,2,3,5")
        print("     • all x 10         → 10 of each provider")
        print("     • back or 0        → Go back")
        print()
        
        while True:
            user_input = input(f"  > Players: ").strip()
            
            result = parse_smart_player_input(user_input, self.providers)
            
            if result.go_back:
                return None, True
            
            if result.error:
                print(f"  ⚠️  {result.error}")
                print(f"  💡 Try: 'gemini x 10' or '1-5' or 'all'")
                continue
            
            if len(result.providers) < 2:
                print(f"  ⚠️  Need at least 2 players for a tournament (you selected {len(result.providers)})")
                continue
            
            # Show selection summary
            provider_counts = {}
            for prov in result.providers:
                provider_counts[prov] = provider_counts.get(prov, 0) + 1
            
            print(f"\n  ✅ Selected {len(result.providers)} players:")
            for prov, count in provider_counts.items():
                print(f"     • {prov}: {count} player{'s' if count > 1 else ''}")
            
            # Confirm if large selection
            if len(result.providers) > 20:
                confirm = input(f"\n  ⚠️  {len(result.providers)} players will create many matches. Continue? [Y/n]: ").strip().lower()
                if confirm in ["n", "no"]:
                    continue
            
            self.config.providers = result.providers
            return self.config.providers, False
    
    def _configure_analysis(self) -> Tuple[Dict, bool]:
        """Step 4: Configure analysis (same as match)."""
        print("\n" + "="*60)
        print("  ✨ STEP 4: Post-Match Analysis")
        print("="*60)
        
        print("\n  Options:")
        print("    1. Full Analysis + Commentary [RECOMMENDED]")
        print("    2. Analysis Only (no commentary)")
        print("    3. Skip Analysis (faster tournaments)")
        print("    0. ← Back")
        
        choice = self._prompt_with_back("Select analysis level", default=1, min_val=1, max_val=3)
        
        if choice == 0:
            return None, True
        
        if choice == 1:
            self.config.enable_analysis = True
            self.config.enable_commentary = True
        elif choice == 2:
            self.config.enable_analysis = True
            self.config.enable_commentary = False
        else:
            self.config.enable_analysis = False
            self.config.enable_commentary = False
        
        return {"analysis": self.config.enable_analysis}, False
    
    def _configure_parallel(self) -> Tuple[Dict, bool]:
        """Step 5: Configure parallel execution (NEW!)."""
        print("\n" + "="*60)
        print("  ⚡ STEP 5: Parallel Execution")
        print("="*60)
        
        total_matches = self._estimate_matches()
        
        print(f"\n  📊 Estimated matches: ~{total_matches}")
        print("\n  Parallel execution runs multiple matches simultaneously using threading.")
        print("  This significantly speeds up tournaments but uses more API quota.")
        print()
        
        print("  Options:")
        print("    1. Sequential (1 match at a time) - Safe, slower")
        print("    2. Parallel - 2 workers - Balanced")
        print("    3. Parallel - 4 workers - Fast [RECOMMENDED for 10+ players]")
        print("    4. Parallel - 8 workers - Very fast (high API usage)")
        print("    5. Parallel - Custom worker count")
        print("    0. ← Back")
        
        choice = self._prompt_with_back("Select execution mode", default=3, min_val=1, max_val=5)
        
        if choice == 0:
            return None, True
        
        if choice == 1:
            self.config.enable_parallel = False
            self.config.max_workers = 1
        elif choice == 2:
            self.config.enable_parallel = True
            self.config.max_workers = 2
        elif choice == 3:
            self.config.enable_parallel = True
            self.config.max_workers = 4
        elif choice == 4:
            self.config.enable_parallel = True
            self.config.max_workers = 8
        else:
            while True:
                workers_str = input(f"  > Number of workers [4]: ").strip()
                if not workers_str:
                    self.config.max_workers = 4
                    break
                try:
                    workers = int(workers_str)
                    if 1 <= workers <= 32:
                        self.config.max_workers = workers
                        break
                    else:
                        print("  ⚠️  Please enter a number between 1 and 32")
                except ValueError:
                    print("  ⚠️  Invalid number")
            
            self.config.enable_parallel = self.config.max_workers > 1
        
        return {"parallel": self.config.enable_parallel, "workers": self.config.max_workers}, False
    
    def _select_export_format(self) -> Tuple[str, bool]:
        """Step 6: Select export format."""
        print("\n" + "="*60)
        print("  📁 STEP 6: Export Format")
        print("="*60)
        
        formats = {
            1: ("html", "HTML (full report) [RECOMMENDED]"),
            2: ("markdown", "Markdown (standings + crosstable)"),
            3: ("json", "JSON (structured data)"),
            4: ("pgn_pretty", "PGN Pretty (all games in one file)"),
            5: ("pgn_strict", "PGN Strict (all games in one file)"),
            6: ("per_game_pgn", "Per-game PGN (individual files)"),
            7: ("all", "ALL formats"),
        }
        
        print("\n  Options:")
        for num, (key, name) in formats.items():
            print(f"    {num}. {name}")
        print("    0. ← Back")
        
        choice = self._prompt_with_back("Select export format", default=1, min_val=1, max_val=len(formats))
        
        if choice == 0:
            return "", True
        
        self.config.export_format = formats[choice][0]
        return self.config.export_format, False
    
    def _set_tournament_name(self) -> Tuple[str, bool]:
        """Step 7: Set tournament name."""
        print("\n" + "="*60)
        print("  📝 STEP 7: Tournament Name")
        print("="*60)
        
        import datetime
        default_name = f"CAISSA Tournament {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        print(f"\n  Default: {default_name}")
        user_input = input(f"  > Tournament name [press Enter for default or 'back']: ").strip()
        
        if user_input.lower() in ["back", "b"]:
            return None, True
        
        self.config.name = user_input if user_input else default_name
        return self.config.name, False
    
    def _confirm_tournament(self) -> Tuple[bool, bool]:
        """Step 8: Confirm configuration."""
        print("\n" + "="*60)
        print("  ✅ TOURNAMENT CONFIGURATION")
        print("="*60)
        
        # Count players by provider
        provider_counts = {}
        for prov in self.config.providers:
            provider_counts[prov] = provider_counts.get(prov, 0) + 1
        
        print(f"\n  📝 Name:          {self.config.name}")
        print(f"  🏆 Format:        {self.config.format}")
        print(f"  ⏱️  Time Control:  {self.config.time_control}")
        print(f"  👥 Players:       {len(self.config.providers)} total")
        for prov, count in provider_counts.items():
            print(f"                    • {prov}: {count}")
        
        analysis_status = "Full Analysis + Commentary" if self.config.enable_commentary else \
                         "Analysis Only" if self.config.enable_analysis else \
                         "No Analysis"
        print(f"  ✨ Analysis:      {analysis_status}")
        
        parallel_status = f"{self.config.max_workers} workers" if self.config.enable_parallel else "Sequential"
        print(f"  ⚡ Execution:     {parallel_status}")
        
        print(f"  📁 Export:        {self.config.export_format}")
        print(f"  📂 Output:        {self.config.output_dir}")
        
        # Estimate time and matches
        total_matches = self._estimate_matches()
        est_time_minutes = self._estimate_time()
        print(f"\n  📊 Est. Matches:  ~{total_matches}")
        print(f"  ⏰ Est. Time:     ~{est_time_minutes} minutes")
        print()
        
        choice_str = input(f"  > Start tournament? [Y/n/back]: ").strip().lower()
        
        if choice_str in ["back", "b"]:
            return False, True
        
        if choice_str in ["n", "no"]:
            return False, False
        
        return True, False
    
    def _estimate_matches(self) -> int:
        """Estimate total number of matches."""
        n = len(self.config.providers)
        
        if self.config.format == "round_robin":
            return n * (n - 1) // 2
        elif self.config.format == "double_round_robin":
            return n * (n - 1)
        elif self.config.format == "swiss":
            return n * 5  # Estimate 5 rounds
        elif self.config.format == "knockout":
            return n - 1
        
        return n
    
    def _estimate_time(self) -> int:
        """Estimate tournament time in minutes."""
        total_matches = self._estimate_matches()
        
        # Estimate time per match based on time control
        time_per_match = {
            "bullet": 2,
            "blitz": 5,
            "rapid": 10,
            "classical": 20,
            "unlimited": 30,
        }.get(self.config.time_control, 10)
        
        # Add analysis overhead if enabled
        if self.config.enable_analysis:
            time_per_match += 2
        
        # Account for parallelization
        if self.config.enable_parallel:
            total_time = (total_matches * time_per_match) / self.config.max_workers
        else:
            total_time = total_matches * time_per_match
        
        return int(total_time)
    
    def _prompt_with_back(self, prompt: str, default: int, min_val: int, max_val: int) -> int:
        """Prompt for integer with validation and back support."""
        while True:
            user_input = input(f"\n  > {prompt} [{default}]: ").strip()
            
            if not user_input:
                return default
            
            if user_input.lower() in ["back", "b", "0"]:
                return 0
            
            try:
                value = int(user_input)
                if min_val <= value <= max_val:
                    return value
                else:
                    print(f"  ⚠️  Please enter a number between {min_val} and {max_val}")
            except ValueError:
                print(f"  ⚠️  Invalid input. Please enter a number.")


# ═══════════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test smart player selection
    providers = ["gemini", "claude", "gpt4", "ollama"]
    
    test_inputs = [
        "gemini x 100",
        "1-3, 5",
        "all x 10",
        "gemini x 50, claude x 30, gpt4 x 20",
        "1,2,3,4,5",
        "all",
        "back",
    ]
    
    print("Testing smart player selection:\n")
    for test in test_inputs:
        result = parse_smart_player_input(test, providers)
        print(f"Input: '{test}'")
        if result.go_back:
            print("  → Go back")
        elif result.error:
            print(f"  → Error: {result.error}")
        else:
            counts = {}
            for p in result.providers:
                counts[p] = counts.get(p, 0) + 1
            print(f"  → {len(result.providers)} players: {counts}")
        print()

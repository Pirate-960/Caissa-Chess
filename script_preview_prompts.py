#!/usr/bin/env python3
"""Preview the system + user prompts for each bias mode.

Usage:
    python script_preview_prompts.py                  # white, black, neutral
    python script_preview_prompts.py --all            # all 5 bias modes
    python script_preview_prompts.py --bias white black draw
"""

import argparse
import sys

from core.prompt_manager import (
    GameContext,
    GameEra,
    PromptBias,
    PromptManager,
)

SEPARATOR = "=" * 80


def preview_bias(pm: PromptManager, bias: PromptBias) -> None:
    """Print system + user prompt for *bias*."""
    ctx = GameContext(
        era=GameEra.ROMANTIC,
        theme=None,
        white_player="Caissa White",
        black_player="Caissa Black",
        aggression_score=7,
        chaos_score=5,
        depth=40,
        blunder_tolerance=1.5,
        bias=bias,
    )

    sys_prompt = pm.build_system_prompt(ctx)
    usr_prompt = pm.build_user_prompt(ctx)

    print(SEPARATOR)
    print(f"  BIAS = {bias.value.upper()}")
    print(SEPARATOR)
    print()
    print("--- SYSTEM PROMPT ---")
    print(sys_prompt)
    print()
    print("--- USER PROMPT ---")
    print(usr_prompt)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview Caissa prompts per bias mode.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Show all 5 bias modes (white, black, draw, random, neutral).",
    )
    parser.add_argument(
        "--bias",
        nargs="+",
        choices=[b.value for b in PromptBias],
        help="Specific bias values to preview.",
    )
    args = parser.parse_args()

    if args.bias:
        biases = [PromptBias(b) for b in args.bias]
    else:
        # Show all 5 bias modes by default
        biases = list(PromptBias)

    pm = PromptManager()

    for bias in biases:
        preview_bias(pm, bias)

    print(SEPARATOR)
    print("Done — previewed", len(biases), "bias mode(s).")


if __name__ == "__main__":
    main()

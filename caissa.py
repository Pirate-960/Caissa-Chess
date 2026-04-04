"""CAISSA - Aesthetic Chess Game Generator using LLMs.

Main CLI entry point.
"""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="CAISSA")
def cli() -> None:
    """CAISSA - Aesthetic Chess Game Generator using LLMs."""
    pass


@cli.command()
def info() -> None:
    """Display information about CAISSA."""
    console.print("[bold cyan]CAISSA[/bold cyan] - Aesthetic Chess Game Generator")
    console.print("Version: [green]0.1.0[/green]")
    console.print("Python: [green]" + sys.version.split()[0] + "[/green]")
    console.print("")
    console.print("Supported LLM providers:")
    providers = [
        ("OpenAI", "GPT-4o, GPT-4o-mini, o1-preview, ..."),
        ("Anthropic", "Claude 3.5 Sonnet, Claude 3 Opus, ..."),
        ("Azure OpenAI", "GPT-4o, GPT-4 Turbo, ..."),
        ("Google Gemini", "Gemini 1.5 Pro, Gemini 2.0 Flash, ..."),
        ("Ollama", "Llama 3.2, Mistral, Mixtral, ..."),
        ("Mock", "For testing without API keys"),
    ]
    for name, models in providers:
        console.print(f"  [bold]{name}[/bold]: {models}")


@cli.command("list-styles")
def list_styles() -> None:
    """List available playing styles."""
    from core.prompt_manager import STYLE_SYSTEM_PROMPTS

    table = Table(title="Available Playing Styles", show_header=True)
    table.add_column("Style", style="bold cyan")
    table.add_column("Description")

    descriptions = {
        "aggressive": "Attacks, sacrifices, and tactical complications",
        "positional": "Pawn structure, piece activity, and strategy",
        "romantic": "Brilliant combinations and king attacks (Morphy/Anderssen style)",
        "defensive": "Safety first, consolidation, and solid positions",
        "balanced": "Weighs both tactical and strategic factors",
    }
    for style in STYLE_SYSTEM_PROMPTS:
        table.add_row(style, descriptions.get(style, ""))
    console.print(table)


@cli.command("list-models")
@click.option("--provider", "-p", default=None, help="Filter by provider name")
def list_models(provider: str | None) -> None:
    """List available LLM models for all providers."""
    from core.llm_provider import (
        AnthropicProvider,
        AzureOpenAIProvider,
        GoogleGeminiProvider,
        MockProvider,
        OllamaProvider,
        OpenAIProvider,
    )

    all_providers: dict[str, type] = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "azure": AzureOpenAIProvider,
        "gemini": GoogleGeminiProvider,
        "ollama": OllamaProvider,
        "mock": MockProvider,
    }

    if provider:
        provider = provider.lower()
        if provider not in all_providers:
            console.print(f"[red]Unknown provider: {provider}[/red]")
            console.print(f"Available: {', '.join(all_providers)}")
            return
        providers_to_show = {provider: all_providers[provider]}
    else:
        providers_to_show = all_providers

    for pname, pcls in providers_to_show.items():
        table = Table(title=f"{pname.title()} Models", show_header=True)
        table.add_column("Model", style="bold cyan")
        table.add_column("Description")
        for model_name, desc in pcls.list_models().items():
            table.add_row(model_name, desc)
        console.print(table)


@cli.command()
@click.option("--provider", "-p", default="mock", help="LLM provider to use")
@click.option("--model", "-m", default=None, help="Model name")
@click.option("--style", "-s", default="balanced", help="Playing style")
@click.option("--max-moves", default=40, help="Maximum moves to generate")
@click.option("--output", "-o", default=None, help="Output PGN file path")
def generate(
    provider: str,
    model: str | None,
    style: str,
    max_moves: int,
    output: str | None,
) -> None:
    """Generate an aesthetic chess game."""
    from core.generator import CaissaGenerator, GenerationConfig
    from core.llm_provider import MockProvider

    console.print(f"[cyan]Generating game with {provider} ({model or 'default model'}) in {style} style...[/cyan]")

    llm = MockProvider()
    config = GenerationConfig(max_moves=max_moves, style=style)
    gen = CaissaGenerator(white_provider=llm, black_provider=llm, config=config)

    with console.status("Generating..."):
        game = gen.generate_game()

    console.print(f"[green]Generated {len(game.moves)} moves[/green]")
    console.print(f"PGN: {game.pgn}")

    if output:
        from export.pgn_builder import PGNBuilder
        builder = PGNBuilder()
        pgn = builder.build_pgn(game.moves)
        builder.save(output, pgn)
        console.print(f"[green]Saved to {output}[/green]")


if __name__ == "__main__":
    cli()

"""CAISSA - Aesthetic Chess Game Generator using LLMs.

Main CLI entry point.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

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


@cli.command()
@click.option("--name", "-n", default="CAISSA Tournament", help="Tournament name")
@click.option("--rounds", "-r", default=1, help="Number of rounds")
@click.option("--style", "-s", default="balanced", help="Playing style")
@click.option("--output-dir", "-o", default="tournament_output", help="Directory for exported files")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["json", "csv", "pgn", "per-game-pgn", "md", "html", "all"]),
    default="all",
    help="Export format",
)
def tournament(
    name: str,
    rounds: int,
    style: str,
    output_dir: str,
    format: str,
) -> None:
    """Run a multi-agent tournament and export results."""
    from match_engine import Tournament, TimeControl
    from core.llm_provider import MockProvider
    from export.tournament_exporter import TournamentExporter, TournamentResult, TournamentStanding
    from aesthetic.beauty_eval import BeautyEvaluator

    console.print(f"[bold cyan]Starting Tournament: {name}[/bold cyan]")
    
    # Setup tournament
    tourney = Tournament(name=name, rounds=rounds, style=style, time_control=TimeControl.BLITZ)
    
    # Add some mock players for demonstration
    # In a real scenario, these would be configured via CLI or config file
    tourney.add_player("Grandmaster Mock", MockProvider(), elo=2800)
    tourney.add_player("Agressive Bot", MockProvider(), elo=2400)
    tourney.add_player("Positional Bot", MockProvider(), elo=2300)

    with console.status("Running matches..."):
        results = tourney.run_round_robin()

    tourney.print_standings()

    # Prepare exporter
    exporter = TournamentExporter(tournament_name=name)
    evaluator = BeautyEvaluator()

    # Add results to exporter
    for i, res in enumerate(results, 1):
        beauty = evaluator.evaluate_game(res.moves)
        exporter.add_result(TournamentResult(
            round_number=(i // len(tourney.players)) + 1,
            white=res.white_player,
            black=res.black_player,
            result=res.result.value,
            white_elo=res.white_elo_before,
            black_elo=res.black_elo_before,
            move_count=len(res.moves),
            aesthetic_score=beauty.overall,
            pgn=res.pgn,
            time_control="BLITZ"
        ))

    # Add standings to exporter
    for i, p in enumerate(tourney.get_standings(), 1):
        exporter.add_standing(TournamentStanding(
            rank=i,
            player=p.name,
            elo=p.elo,
            wins=p.wins,
            losses=p.losses,
            draws=p.draws,
            points=p.points,
            games_played=p.games_played
        ))

    # Export based on choice
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[cyan]Exporting results to {output_dir}...[/cyan]")

    if format == "json" or format == "all":
        exporter.export_json(out_path / "tournament.json")
    if format == "csv" or format == "all":
        exporter.export_csv(out_path / "tournament.csv")
    if format == "pgn" or format == "all":
        exporter.export_pgn_bundle(out_path / "tournament.pgn")
    if format == "per-game-pgn" or format == "all":
        exporter.export_per_game_pgn(out_path / "games")
    if format == "md" or format == "all":
        exporter.export_markdown(out_path / "report.md")
    if format == "html" or format == "all":
        exporter.export_html(out_path / "report.html")

    console.print("[bold green]Tournament complete and results exported![/bold green]")


if __name__ == "__main__":
    cli()

"""
core/batch_engine.py

Advanced batch generation engine for Caissa Chess.

Features:
- Sequential and parallel (thread-pool) generation modes
- Quality-gated generation — regenerate until threshold met
- Style variation modes: fixed, round-robin, random, weighted
- Theme and era rotation across games
- Resume interrupted batches — skip existing output files
- Multi-format export per game (PGN, HTML, Markdown, JSON)
- Configurable naming patterns with token substitution
- Fail-fast or best-effort error handling
- Real-time progress callbacks for the CLI
- Batch summary report generation (Markdown / HTML)
- Full integration with CaissaGenerator, StyleSlider, and export pipeline
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import chess

from core.generator import (
    CaissaGenerator,
    GenerationQuality,
    GenerationResult,
    GenerationStats,
)
from core.prompt_manager import GameContext, GameEra, GameTheme, NarrativeArc, PromptBias
from aesthetic.style_slider import StyleSlider, StylePreset

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class BatchMode(str, Enum):
    """How games are generated."""
    SEQUENTIAL = "sequential"     # One at a time
    PARALLEL = "parallel"         # ThreadPoolExecutor


class StyleVariation(str, Enum):
    """How styles rotate across games."""
    FIXED = "fixed"               # Same style for every game
    ROUND_ROBIN = "round_robin"   # Cycle through chosen styles
    RANDOM = "random"             # Random per game from pool
    WEIGHTED = "weighted"         # Weighted random from pool


class BatchJobStatus(str, Enum):
    """Per-job lifecycle."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"           # Resume detected existing file


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BatchConfig:
    """Full configuration for a batch run."""

    # ── Core ─────────────────────────────────────────────────────────────────
    count: int = 5
    mode: BatchMode = BatchMode.SEQUENTIAL
    workers: int = 4              # Thread count when mode == PARALLEL

    # ── Styles ───────────────────────────────────────────────────────────────
    styles: List[str] = field(default_factory=lambda: ["tal"])
    style_variation: StyleVariation = StyleVariation.FIXED
    style_weights: Dict[str, float] = field(default_factory=dict)

    # ── Themes & Eras ────────────────────────────────────────────────────────
    themes: List[str] = field(default_factory=list)       # empty → no theme
    eras: List[str] = field(default_factory=lambda: ["romantic"])

    # ── Quality Gate ─────────────────────────────────────────────────────────
    min_quality: str = "acceptable"   # GenerationQuality name
    quality_retries: int = 3          # Attempts per game to hit quality

    # ── Generation ───────────────────────────────────────────────────────────
    depth: int = 40                   # Target half-moves per game
    aggression: Optional[int] = None  # Override; None → from style
    chaos: Optional[int] = None       # Override; None → from style
    bias: str = "neutral"             # "white", "black", or "neutral"
    narrative_arcs: List[str] = field(default_factory=list)

    # ── Player Names ─────────────────────────────────────────────────────────
    white_player: str = "Caissa White"
    black_player: str = "Caissa Black"
    auto_name_players: bool = True    # Use style name for player names

    # ── Output ───────────────────────────────────────────────────────────────
    output_dir: str = "./games"
    filename_pattern: str = "game_{n:03d}"  # Tokens: {n}, {style}, {theme}, {era}, {date}
    export_formats: List[str] = field(default_factory=lambda: ["pgn"])
    pretty_pgn: bool = True

    # ── Resilience ───────────────────────────────────────────────────────────
    fail_fast: bool = False           # Abort entire batch on first error
    resume: bool = True               # Skip games whose output already exists
    max_retries_per_game: int = 3     # LLM-level retries inside generator

    # ── Reporting ────────────────────────────────────────────────────────────
    generate_summary: bool = True     # Write a summary report after batch
    summary_format: str = "markdown"  # "markdown" | "html"

    # ── Misc ─────────────────────────────────────────────────────────────────
    seed: Optional[int] = None        # Reproducible randomness

    def resolved_min_quality(self) -> GenerationQuality:
        """Parse the min_quality string into the enum."""
        mapping = {
            "excellent": GenerationQuality.EXCELLENT,
            "good": GenerationQuality.GOOD,
            "acceptable": GenerationQuality.ACCEPTABLE,
            "poor": GenerationQuality.POOR,
            "failed": GenerationQuality.FAILED,
        }
        return mapping.get(self.min_quality.lower(), GenerationQuality.ACCEPTABLE)


@dataclass
class BatchJob:
    """Single game within a batch."""
    index: int                        # 1-based
    style: str
    era: str
    theme: Optional[str] = None
    narrative_arc: Optional[str] = None
    depth: int = 40
    aggression: int = 7
    chaos: int = 5
    white_player: str = "Caissa White"
    black_player: str = "Caissa Black"

    # ── Runtime state ────────────────────────────────────────────────────────
    status: BatchJobStatus = BatchJobStatus.PENDING
    result: Optional[GenerationResult] = None
    pgn_string: str = ""
    moves: List[str] = field(default_factory=list)
    attempts: int = 0
    elapsed: float = 0.0
    error: Optional[str] = None
    output_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "style": self.style,
            "era": self.era,
            "theme": self.theme,
            "narrative_arc": self.narrative_arc,
            "status": self.status.value,
            "attempts": self.attempts,
            "elapsed": round(self.elapsed, 2),
            "moves": len(self.moves),
            "error": self.error,
            "output_files": self.output_files,
        }


@dataclass
class BatchSummary:
    """Aggregate results of a batch run."""
    total: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    total_time: float = 0.0
    jobs: List[BatchJob] = field(default_factory=list)

    # Derived stats — populated by finalize()
    quality_distribution: Dict[str, int] = field(default_factory=dict)
    style_distribution: Dict[str, int] = field(default_factory=dict)
    avg_beauty: float = 0.0
    avg_moves: float = 0.0
    avg_time_per_game: float = 0.0
    best_game_index: Optional[int] = None
    worst_game_index: Optional[int] = None

    def finalize(self) -> None:
        """Compute derived statistics once all jobs are done."""
        beauty_scores: List[float] = []
        move_counts: List[int] = []
        gen_times: List[float] = []

        for job in self.jobs:
            if job.status == BatchJobStatus.SUCCESS:
                self.style_distribution[job.style] = (
                    self.style_distribution.get(job.style, 0) + 1
                )
                move_counts.append(len(job.moves))
                gen_times.append(job.elapsed)

                if job.result and job.result.beauty_score is not None:
                    beauty_scores.append(job.result.beauty_score)

                quality = (
                    job.result.quality.value if job.result else "unknown"
                )
                self.quality_distribution[quality] = (
                    self.quality_distribution.get(quality, 0) + 1
                )

        if beauty_scores:
            self.avg_beauty = sum(beauty_scores) / len(beauty_scores)
            self.best_game_index = self.jobs[
                beauty_scores.index(max(beauty_scores))
            ].index
            self.worst_game_index = self.jobs[
                beauty_scores.index(min(beauty_scores))
            ].index

        if move_counts:
            self.avg_moves = sum(move_counts) / len(move_counts)
        if gen_times:
            self.avg_time_per_game = sum(gen_times) / len(gen_times)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "successful": self.successful,
            "failed": self.failed,
            "skipped": self.skipped,
            "total_time": round(self.total_time, 2),
            "avg_time_per_game": round(self.avg_time_per_game, 2),
            "avg_moves": round(self.avg_moves, 1),
            "avg_beauty": round(self.avg_beauty, 1),
            "quality_distribution": self.quality_distribution,
            "style_distribution": self.style_distribution,
            "best_game_index": self.best_game_index,
            "worst_game_index": self.worst_game_index,
            "jobs": [j.to_dict() for j in self.jobs],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PROGRESS CALLBACK TYPE
# ═══════════════════════════════════════════════════════════════════════════════

# on_progress(job_index, total, status, message)
ProgressCallback = Callable[[int, int, BatchJobStatus, str], None]


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class BatchEngine:
    """
    Orchestrates batch game generation.

    Usage::

        engine = BatchEngine(config, provider, stockfish_path)
        summary = engine.run(on_progress=my_callback)
    """

    def __init__(
        self,
        config: BatchConfig,
        provider,                       # LLMProvider (any)
        stockfish_path: Optional[str] = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.stockfish_path = stockfish_path
        self._slider = StyleSlider()
        self._rng = random.Random(config.seed)
        self._lock = threading.Lock()   # Protects summary counters in parallel mode

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC
    # ─────────────────────────────────────────────────────────────────────────

    def plan_jobs(self) -> List[BatchJob]:
        """
        Pre-plan all jobs so the user can review before executing.

        Returns a list of :class:`BatchJob` in PENDING state.
        """
        cfg = self.config
        jobs: List[BatchJob] = []

        styles_pool = self._resolve_styles()
        themes_pool = self._resolve_themes()
        eras_pool = self._resolve_eras()
        arcs_pool = self._resolve_narrative_arcs()

        for i in range(cfg.count):
            idx = i + 1
            style = self._pick_style(i, styles_pool)
            theme = self._pick_rotating(i, themes_pool)
            era = self._pick_rotating(i, eras_pool)
            arc = self._pick_rotating(i, arcs_pool)

            # Resolve aggression / chaos from style if not overridden
            try:
                style_enum = StylePreset(style)
                style_cfg = self._slider.get_config(style_enum)
                aggression = cfg.aggression if cfg.aggression is not None else style_cfg.aggression
                chaos = cfg.chaos if cfg.chaos is not None else style_cfg.chaos
            except (ValueError, KeyError):
                aggression = cfg.aggression or 7
                chaos = cfg.chaos or 5

            # Player names
            if cfg.auto_name_players:
                white = f"Caissa {style.replace('_', ' ').title()}"
                black = "Caissa Opponent"
            else:
                white = cfg.white_player
                black = cfg.black_player

            jobs.append(BatchJob(
                index=idx,
                style=style,
                era=era,
                theme=theme,
                narrative_arc=arc,
                depth=cfg.depth,
                aggression=aggression,
                chaos=chaos,
                white_player=white,
                black_player=black,
            ))

        return jobs

    def run(
        self,
        on_progress: Optional[ProgressCallback] = None,
    ) -> BatchSummary:
        """
        Execute the batch.  Blocks until complete.

        Args:
            on_progress: Optional callback ``(job_index, total, status, msg)``.

        Returns:
            :class:`BatchSummary` with all results.
        """
        cfg = self.config
        jobs = self.plan_jobs()
        out_dir = Path(cfg.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        summary = BatchSummary(total=len(jobs), jobs=jobs)
        start = time.time()

        logger.info(
            "Batch run starting: count=%d, mode=%s, workers=%d, styles=%s, "
            "quality_gate=%s, resume=%s",
            len(jobs), cfg.mode.value, cfg.workers, cfg.styles,
            cfg.min_quality, cfg.resume,
        )

        # ── Handle resume — skip existing files ─────────────────────────────
        if cfg.resume:
            self._mark_skippable(jobs, out_dir)
            for job in jobs:
                if job.status == BatchJobStatus.SKIPPED:
                    summary.skipped += 1
                    if on_progress:
                        on_progress(job.index, len(jobs), BatchJobStatus.SKIPPED,
                                    "Skipped (file exists)")

        # ── Filter to pending jobs only ──────────────────────────────────────
        pending = [j for j in jobs if j.status == BatchJobStatus.PENDING]

        if not pending:
            logger.info("All games already exist — nothing to do.")
        elif cfg.mode == BatchMode.PARALLEL and cfg.workers > 1:
            self._run_parallel(pending, out_dir, summary, on_progress)
        else:
            self._run_sequential(pending, out_dir, summary, on_progress)

        summary.total_time = time.time() - start
        summary.finalize()

        if cfg.generate_summary:
            self._write_summary_report(summary, out_dir)

        logger.info(
            "Batch complete: %d/%d OK, %d failed, %d skipped, %.1fs total",
            summary.successful, summary.total, summary.failed,
            summary.skipped, summary.total_time,
        )

        return summary

    # ─────────────────────────────────────────────────────────────────────────
    # SEQUENTIAL RUNNER
    # ─────────────────────────────────────────────────────────────────────────

    def _run_sequential(
        self,
        jobs: List[BatchJob],
        out_dir: Path,
        summary: BatchSummary,
        on_progress: Optional[ProgressCallback],
    ) -> None:
        with CaissaGenerator(
            provider=self.provider,
            stockfish_path=self.stockfish_path,
        ) as gen:
            for job in jobs:
                if on_progress:
                    on_progress(job.index, summary.total, BatchJobStatus.RUNNING,
                                f"Generating game {job.index}...")
                self._execute_job(job, gen, out_dir)
                self._tally(job, summary)
                if on_progress:
                    msg = self._status_message(job)
                    on_progress(job.index, summary.total, job.status, msg)
                if self.config.fail_fast and job.status == BatchJobStatus.FAILED:
                    logger.warning("Fail-fast triggered at game %d", job.index)
                    break

    # ─────────────────────────────────────────────────────────────────────────
    # PARALLEL RUNNER
    # ─────────────────────────────────────────────────────────────────────────

    def _run_parallel(
        self,
        jobs: List[BatchJob],
        out_dir: Path,
        summary: BatchSummary,
        on_progress: Optional[ProgressCallback],
    ) -> None:
        workers = min(self.config.workers, len(jobs))
        logger.info("Starting parallel batch with %d workers", workers)

        # Each thread gets its own generator (separate Stockfish process).
        def _worker(job: BatchJob) -> BatchJob:
            with CaissaGenerator(
                provider=self.provider,
                stockfish_path=self.stockfish_path,
            ) as gen:
                self._execute_job(job, gen, out_dir)
            return job

        fail_fast_event = threading.Event()

        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_to_job: Dict[Future, BatchJob] = {}
            for job in jobs:
                if fail_fast_event.is_set():
                    break
                if on_progress:
                    on_progress(job.index, summary.total, BatchJobStatus.RUNNING,
                                f"Generating game {job.index}...")
                future_to_job[pool.submit(_worker, job)] = job

            for future in as_completed(future_to_job):
                job = future_to_job[future]
                try:
                    future.result()  # propagate exceptions
                except Exception as exc:
                    job.status = BatchJobStatus.FAILED
                    job.error = str(exc)
                    logger.error("Parallel job %d raised: %s", job.index, exc,
                                 exc_info=True)

                with self._lock:
                    self._tally(job, summary)

                if on_progress:
                    msg = self._status_message(job)
                    on_progress(job.index, summary.total, job.status, msg)

                if self.config.fail_fast and job.status == BatchJobStatus.FAILED:
                    fail_fast_event.set()
                    logger.warning("Fail-fast triggered at game %d", job.index)

    # ─────────────────────────────────────────────────────────────────────────
    # JOB EXECUTION (one game)
    # ─────────────────────────────────────────────────────────────────────────

    def _execute_job(
        self,
        job: BatchJob,
        gen: CaissaGenerator,
        out_dir: Path,
    ) -> None:
        """Generate one game for *job*, respecting quality gate & retries."""
        cfg = self.config
        job.status = BatchJobStatus.RUNNING
        t0 = time.time()

        context = self._build_context(job)
        min_quality = cfg.resolved_min_quality()
        max_attempts = max(cfg.quality_retries, 1)

        best_result: Optional[Tuple[bool, str, List[str]]] = None
        best_quality = GenerationQuality.FAILED

        quality_rank = {
            GenerationQuality.EXCELLENT: 4,
            GenerationQuality.GOOD: 3,
            GenerationQuality.ACCEPTABLE: 2,
            GenerationQuality.POOR: 1,
            GenerationQuality.FAILED: 0,
        }

        for attempt in range(1, max_attempts + 1):
            job.attempts = attempt
            try:
                success, pgn_string, moves = gen.generate_game(context)
            except Exception as exc:
                logger.error("Job %d attempt %d error: %s", job.index, attempt, exc)
                continue

            if not success:
                continue

            # Assess quality
            beauty = None
            try:
                beauty = gen.beauty_evaluator.evaluate_game(moves)
            except Exception:
                pass
            quality = gen._assess_quality(moves, beauty)

            if (best_result is None
                    or quality_rank.get(quality, 0) > quality_rank.get(best_quality, 0)):
                best_result = (success, pgn_string, moves)
                best_quality = quality
                job.result = GenerationResult(
                    success=True,
                    pgn=pgn_string,
                    moves=moves,
                    quality=quality,
                    beauty_score=beauty,
                    generation_time=time.time() - t0,
                    attempts_used=attempt,
                )

            if quality_rank.get(quality, 0) >= quality_rank.get(min_quality, 0):
                logger.info(
                    "Job %d met quality gate (%s) on attempt %d",
                    job.index, quality.value, attempt,
                )
                break
        else:
            if best_result is not None:
                logger.info(
                    "Job %d did not meet quality gate; using best result (%s)",
                    job.index, best_quality.value,
                )

        job.elapsed = time.time() - t0

        if best_result:
            success, pgn_string, moves = best_result
            job.pgn_string = pgn_string
            job.moves = moves
            job.status = BatchJobStatus.SUCCESS
            self._export_game(job, out_dir)
        else:
            job.status = BatchJobStatus.FAILED
            job.error = "All attempts failed to produce a valid game"

    # ─────────────────────────────────────────────────────────────────────────
    # EXPORT
    # ─────────────────────────────────────────────────────────────────────────

    def _export_game(self, job: BatchJob, out_dir: Path) -> None:
        """Export game in all requested formats via the unified export pipeline."""
        from export.annotation_parser import parse_pgn
        from export.game_exporter import GameExporter

        cfg = self.config
        base = self._resolve_filename(job)

        # ── Parse once, export many ──────────────────────────────
        parsed_game = parse_pgn(job.pgn_string)

        # Enrich headers that the LLM may not have set
        if not parsed_game.headers.get("White") or parsed_game.headers.get("White") == "?":
            parsed_game.headers["White"] = job.white_player
        if not parsed_game.headers.get("Black") or parsed_game.headers.get("Black") == "?":
            parsed_game.headers["Black"] = job.black_player
        if not parsed_game.headers.get("Round") or parsed_game.headers.get("Round") == "?":
            parsed_game.headers["Round"] = str(job.index)

        beauty_score = (
            job.result.beauty_score if job.result and job.result.beauty_score is not None else None
        )

        exporter = GameExporter(
            game=parsed_game,
            beauty_score=beauty_score,
            style_name=job.style,
        )

        for fmt in cfg.export_formats:
            fmt_lower = fmt.lower().strip()
            ext = {
                "pgn": ".pgn", "html": ".html",
                "markdown": ".md", "md": ".md",
                "json": ".json",
            }.get(fmt_lower, ".pgn")
            filepath = out_dir / f"{base}{ext}"

            try:
                content = exporter.export(fmt_lower)
                filepath.write_text(content, encoding="utf-8")
                job.output_files.append(str(filepath))
                logger.info("Exported job %d → %s", job.index, filepath)

            except Exception as exc:
                # Fallback: write raw PGN so the game isn't lost
                logger.error(
                    "Export failed for job %d (%s): %s — falling back to raw PGN",
                    job.index, fmt_lower, exc,
                )
                try:
                    fallback = out_dir / f"{base}.pgn"
                    if not fallback.exists():
                        fallback.write_text(job.pgn_string, encoding="utf-8")
                        job.output_files.append(str(fallback))
                except Exception:
                    pass

    # ─────────────────────────────────────────────────────────────────────────
    # SUMMARY REPORT
    # ─────────────────────────────────────────────────────────────────────────

    def _write_summary_report(self, summary: BatchSummary, out_dir: Path) -> None:
        """Write the batch summary report to disk."""
        cfg = self.config
        fmt = cfg.summary_format.lower()

        if fmt == "html":
            content = self._summary_to_html(summary)
            filepath = out_dir / "batch_summary.html"
        else:
            content = self._summary_to_markdown(summary)
            filepath = out_dir / "batch_summary.md"

        try:
            filepath.write_text(content, encoding="utf-8")
            logger.info("Batch summary → %s", filepath)
        except Exception as exc:
            logger.error("Failed to write summary: %s", exc)

        # Also write machine-readable JSON
        json_path = out_dir / "batch_summary.json"
        try:
            json_path.write_text(
                json.dumps(summary.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Failed to write JSON summary: %s", exc)

    def _summary_to_markdown(self, summary: BatchSummary) -> str:
        lines = [
            "# Caissa Batch Generation Summary",
            "",
            f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
            f"**Total Games:** {summary.total}  ",
            f"**Successful:** {summary.successful}  ",
            f"**Failed:** {summary.failed}  ",
            f"**Skipped (resumed):** {summary.skipped}  ",
            f"**Total Time:** {summary.total_time:.1f}s  ",
            f"**Avg Time/Game:** {summary.avg_time_per_game:.1f}s  ",
            f"**Avg Moves/Game:** {summary.avg_moves:.0f}  ",
            f"**Avg Beauty Score:** {summary.avg_beauty:.1f}  ",
            "",
        ]
        if summary.quality_distribution:
            lines += ["## Quality Distribution", ""]
            for q, n in sorted(summary.quality_distribution.items()):
                lines.append(f"- **{q}:** {n}")
            lines.append("")

        if summary.style_distribution:
            lines += ["## Style Distribution", ""]
            for s, n in sorted(summary.style_distribution.items()):
                lines.append(f"- **{s}:** {n}")
            lines.append("")

        lines += ["## Per-Game Details", "", "| # | Style | Moves | Beauty | Quality | Time | Status |",
                   "|---|-------|-------|--------|---------|------|--------|"]
        for job in summary.jobs:
            beauty = (
                f"{job.result.beauty_score:.1f}"
                if job.result and job.result.beauty_score is not None
                else "—"
            )
            quality = job.result.quality.value if job.result else "—"
            moves = len(job.moves) if job.moves else 0
            lines.append(
                f"| {job.index} | {job.style} | {moves} | {beauty} "
                f"| {quality} | {job.elapsed:.1f}s | {job.status.value} |"
            )
        lines.append("")
        return "\n".join(lines)

    def _summary_to_html(self, summary: BatchSummary) -> str:
        rows = []
        for job in summary.jobs:
            beauty = (
                f"{job.result.beauty_score:.1f}"
                if job.result and job.result.beauty_score is not None
                else "—"
            )
            quality = job.result.quality.value if job.result else "—"
            moves = len(job.moves) if job.moves else 0
            status_color = {
                "success": "#2a7",
                "failed": "#d44",
                "skipped": "#888",
            }.get(job.status.value, "#555")
            rows.append(
                f"<tr><td>{job.index}</td><td>{job.style}</td>"
                f"<td>{moves}</td><td>{beauty}</td><td>{quality}</td>"
                f"<td>{job.elapsed:.1f}s</td>"
                f"<td style='color:{status_color}'>{job.status.value}</td></tr>"
            )

        return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\">
<title>Caissa Batch Summary</title>
<style>
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; max-width: 960px;
         margin: 2rem auto; padding: 0 1rem; color: #222; }}
  h1 {{ border-bottom: 2px solid #333; padding-bottom: .4rem; }}
  .stats {{ display: grid; grid-template-columns: repeat(4, 1fr);
            gap: .8rem; margin: 1.5rem 0; }}
  .stat {{ background: #f5f5f5; padding: .8rem; border-radius: 6px; text-align: center; }}
  .stat .value {{ font-size: 1.6rem; font-weight: 700; }}
  .stat .label {{ font-size: .85rem; color: #666; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
  th, td {{ padding: .5rem .7rem; text-align: left; border-bottom: 1px solid #ddd; }}
  th {{ background: #333; color: #fff; }}
  tr:hover {{ background: #f9f9f9; }}
</style>
</head>
<body>
<h1>Caissa Batch Summary</h1>
<p>{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
<div class=\"stats\">
  <div class=\"stat\"><div class=\"value\">{summary.successful}/{summary.total}</div>
    <div class=\"label\">Successful</div></div>
  <div class=\"stat\"><div class=\"value\">{summary.total_time:.1f}s</div>
    <div class=\"label\">Total Time</div></div>
  <div class=\"stat\"><div class=\"value\">{summary.avg_beauty:.1f}</div>
    <div class=\"label\">Avg Beauty</div></div>
  <div class=\"stat\"><div class=\"value\">{summary.avg_moves:.0f}</div>
    <div class=\"label\">Avg Moves</div></div>
</div>
<table>
<tr><th>#</th><th>Style</th><th>Moves</th><th>Beauty</th><th>Quality</th><th>Time</th><th>Status</th></tr>
{"".join(rows)}
</table>
</body>
</html>"""

    # ─────────────────────────────────────────────────────────────────────────
    # INTERNAL HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _build_context(self, job: BatchJob) -> GameContext:
        """Translate a BatchJob into a GameContext for the generator."""
        era_map = {
            "romantic": GameEra.ROMANTIC,
            "classical": GameEra.CLASSICAL,
            "hypermodern": GameEra.HYPERMODERN,
            "soviet": GameEra.SOVIET,
            "computer": GameEra.COMPUTER,
            "neural": GameEra.NEURAL,
        }
        theme_map = {
            "queen_sacrifice": GameTheme.QUEEN_SACRIFICE,
            "rook_sacrifice": GameTheme.ROOK_SACRIFICE,
            "windmill": GameTheme.WINDMILL,
            "minority_attack": GameTheme.MINORITY_ATTACK,
            "pawn_storm": GameTheme.PAWN_STORM,
            "quiet_killer": GameTheme.QUIET_KILLER,
            "perpetual_check": GameTheme.PERPETUAL_CHECK,
            "stalemate_trap": GameTheme.STALEMATE_TRAP,
            "back_rank": GameTheme.BACK_RANK,
            "fianchetto": GameTheme.FIANCHETTO,
        }

        era = era_map.get(job.era.lower(), GameEra.ROMANTIC)
        theme = theme_map.get(job.theme, None) if job.theme else None

        bias_map = {
            "white": PromptBias.WHITE,
            "black": PromptBias.BLACK,
            "draw": PromptBias.DRAW,
            "random": PromptBias.RANDOM,
            "neutral": PromptBias.NEUTRAL,
        }
        game_bias = bias_map.get(
            self.config.bias.lower(), PromptBias.NEUTRAL
        )

        return GameContext(
            era=era,
            theme=theme,
            white_player=job.white_player,
            black_player=job.black_player,
            aggression_score=job.aggression,
            chaos_score=job.chaos,
            depth=job.depth,
            bias=game_bias,
        )

    def _resolve_styles(self) -> List[str]:
        """Expand style list, defaulting to the single configured style."""
        cfg = self.config
        if not cfg.styles:
            return ["tal"]
        return list(cfg.styles)

    def _resolve_themes(self) -> List[Optional[str]]:
        """Themes list; empty means no themes at all (returns [None])."""
        if not self.config.themes:
            return [None]
        return list(self.config.themes)

    def _resolve_eras(self) -> List[str]:
        if not self.config.eras:
            return ["romantic"]
        return list(self.config.eras)

    def _resolve_narrative_arcs(self) -> List[Optional[str]]:
        if not self.config.narrative_arcs:
            return [None]
        return list(self.config.narrative_arcs)

    def _pick_style(self, index: int, pool: List[str]) -> str:
        """Select style according to variation mode."""
        cfg = self.config
        if cfg.style_variation == StyleVariation.FIXED:
            return pool[0]
        elif cfg.style_variation == StyleVariation.ROUND_ROBIN:
            return pool[index % len(pool)]
        elif cfg.style_variation == StyleVariation.RANDOM:
            return self._rng.choice(pool)
        elif cfg.style_variation == StyleVariation.WEIGHTED:
            weights = [cfg.style_weights.get(s, 1.0) for s in pool]
            return self._rng.choices(pool, weights=weights, k=1)[0]
        return pool[0]

    def _pick_rotating(self, index: int, pool: list):
        """Rotate through a pool or return None."""
        if not pool or pool == [None]:
            return None
        return pool[index % len(pool)]

    def _resolve_filename(self, job: BatchJob) -> str:
        """Apply token substitution to the filename pattern."""
        pattern = self.config.filename_pattern
        now = datetime.now()
        try:
            return pattern.format(
                n=job.index,
                style=job.style,
                era=job.era.replace(" ", "_").lower(),
                theme=job.theme or "none",
                date=now.strftime("%Y%m%d"),
                time=now.strftime("%H%M%S"),
            )
        except (KeyError, IndexError, ValueError):
            return f"game_{job.index:03d}"

    def _mark_skippable(self, jobs: List[BatchJob], out_dir: Path) -> None:
        """Mark jobs whose primary output file already exists."""
        primary_ext = {"pgn": ".pgn", "html": ".html", "markdown": ".md",
                       "json": ".json"}.get(
            self.config.export_formats[0].lower() if self.config.export_formats else "pgn",
            ".pgn",
        )
        for job in jobs:
            fname = self._resolve_filename(job) + primary_ext
            if (out_dir / fname).exists():
                job.status = BatchJobStatus.SKIPPED
                logger.info("Job %d skipped — %s already exists", job.index, fname)

    def _tally(self, job: BatchJob, summary: BatchSummary) -> None:
        """Increment summary counters for a completed job."""
        if job.status == BatchJobStatus.SUCCESS:
            summary.successful += 1
        elif job.status == BatchJobStatus.FAILED:
            summary.failed += 1

    @staticmethod
    def _status_message(job: BatchJob) -> str:
        if job.status == BatchJobStatus.SUCCESS:
            beauty = ""
            if job.result and job.result.beauty_score is not None:
                beauty = f", beauty={job.result.beauty_score:.0f}"
            return (
                f"OK ({len(job.moves)} moves, {job.elapsed:.1f}s, "
                f"style={job.style}{beauty})"
            )
        elif job.status == BatchJobStatus.FAILED:
            return f"FAILED: {job.error or 'unknown'}"
        elif job.status == BatchJobStatus.SKIPPED:
            return "Skipped (file exists)"
        return job.status.value

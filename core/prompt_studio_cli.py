"""Prompt Studio CLI module extracted from main.py."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _preview_template(name: str, template_payload: dict, preview_lines: int, *, io: dict):
    from core.prompt_manager import PromptManager, GameContext, GameEra, PromptBias

    print_info = io["print_info"]
    print_warning = io["print_warning"]
    print_error = io["print_error"]
    C = io["C"]

    system_template = template_payload.get("system_template", "")
    report = PromptManager.lint_system_template(system_template)
    badges = PromptManager.compatibility_badges(system_template)
    print_info(f"Template preview: {name}")
    print_info(
        f"Compatibility: single {'✅' if badges['single'] else '⚠'} | "
        f"match {'✅' if badges['match'] else '⚠'} | "
        f"tournament {'✅' if badges['tournament'] else '⚠'}"
    )
    print_info(f"Lint: strict_errors={len(report['strict_errors'])}, warnings={len(report['warnings'])}")
    for err in report["strict_errors"][:5]:
        print_error(err)
    for warn in report["warnings"][:8]:
        print_warning(warn)
    sample = GameContext(
        era=GameEra.ROMANTIC,
        theme=None,
        white_player="Caissa White",
        black_player="Caissa Black",
        aggression_score=7,
        chaos_score=5,
        depth=40,
        bias=PromptBias.NEUTRAL,
    )
    pm = PromptManager()
    old_catalog = PromptManager.get_prompt_catalog()
    try:
        PromptManager.set_prompt_overrides(
            system_template=template_payload.get("system_template"),
            user_prompt_prefix=template_payload.get("user_prompt_prefix"),
            user_prompt_suffix=template_payload.get("user_prompt_suffix"),
        )
        s = pm.build_system_prompt(sample)
        u = pm.build_user_prompt(sample)
        print_info(f"Size: system={len(s)} chars, user={len(u)} chars, est_tokens~{(len(s)+len(u))//4}")
        print(f"\n  {C.BOLD}System preview (first {preview_lines if preview_lines > 0 else 'all'} lines){C.RESET}")
        lines = s.splitlines()
        selected_lines = lines if preview_lines <= 0 else lines[:preview_lines]
        for line in selected_lines:
            print(f"  {line}")
    finally:
        PromptManager.set_prompt_overrides(
            system_template=old_catalog.get("system_template"),
            user_prompt_prefix=old_catalog.get("user_prompt_prefix"),
            user_prompt_suffix=old_catalog.get("user_prompt_suffix"),
        )


def _print_system_template_comparison(name_a: str, t1: str, name_b: str, t2: str, view_mode: str, *, io: dict):
    import difflib
    from core.prompt_manager import PromptManager

    print_info = io["print_info"]
    C = io["C"]

    r1 = PromptManager.lint_system_template(t1)
    r2 = PromptManager.lint_system_template(t2)
    b1 = PromptManager.compatibility_badges(t1)
    b2 = PromptManager.compatibility_badges(t2)
    print_info(f"A: {name_a}")
    print_info(f"   single {'✅' if b1['single'] else '⚠'} | strict_errors={len(r1['strict_errors'])} | warnings={len(r1['warnings'])}")
    print_info(f"B: {name_b}")
    print_info(f"   single {'✅' if b2['single'] else '⚠'} | strict_errors={len(r2['strict_errors'])} | warnings={len(r2['warnings'])}")
    lines_a = t1.splitlines()
    lines_b = t2.splitlines()
    if lines_a == lines_b:
        print_info("No differences found.")
        return

    if view_mode == "summary":
        sm = difflib.SequenceMatcher(a=lines_a, b=lines_b)
        opcodes = sm.get_opcodes()
        added = sum((b2 - b1) for tag, _, _, b1, b2 in opcodes if tag == "insert")
        removed = sum((a2 - a1) for tag, a1, a2, _, _ in opcodes if tag == "delete")
        changed = sum(max(a2 - a1, b2 - b1) for tag, a1, a2, b1, b2 in opcodes if tag == "replace")
        print_info(f"Summary: +{added} / -{removed} / ~{changed} lines changed")
        return

    if view_mode == "unified":
        diff = list(difflib.unified_diff(lines_a, lines_b, fromfile=name_a, tofile=name_b, lineterm=""))
        print_info("System template diff (unified, first 120 lines):")
        for line in diff[:120]:
            color = C.GREEN if line.startswith("+") and not line.startswith("+++") else C.RED if line.startswith("-") and not line.startswith("---") else C.DIM
            print(f"{color}{line}{C.RESET}")
        if len(diff) > 120:
            print(f"{C.DIM}... ({len(diff)-120} more diff lines){C.RESET}")
        return

    print_info("System template diff (side-by-side, first 80 rows):")
    width = 160
    try:
        width = os.get_terminal_size().columns
    except OSError:
        pass
    col_width = max(30, (width - 7) // 2)
    print(f"{C.BOLD}{name_a[:col_width].ljust(col_width)} | {name_b[:col_width].ljust(col_width)}{C.RESET}")
    print(f"{C.DIM}{'-' * col_width}-+-{'-' * col_width}{C.RESET}")
    sm = difflib.SequenceMatcher(a=lines_a, b=lines_b)
    rendered = 0
    for tag, a1, a2, b1, b2 in sm.get_opcodes():
        if tag == "equal":
            continue
        max_len = max(a2 - a1, b2 - b1)
        for i in range(max_len):
            left = lines_a[a1 + i] if (a1 + i) < a2 else ""
            right = lines_b[b1 + i] if (b1 + i) < b2 else ""
            mark_l = "-" if left and (not right or left != right) else " "
            mark_r = "+" if right and (not left or left != right) else " "
            left_cell = f"{mark_l} {left}"[:col_width].ljust(col_width)
            right_cell = f"{mark_r} {right}"[:col_width].ljust(col_width)
            l_color = io["C"].RED if mark_l == "-" else io["C"].DIM
            r_color = io["C"].GREEN if mark_r == "+" else io["C"].DIM
            print(f"{l_color}{left_cell}{io['C'].RESET} | {r_color}{right_cell}{io['C'].RESET}")
            rendered += 1
            if rendered >= 80:
                print(f"{io['C'].DIM}... (truncated; switch to unified for full context){io['C'].RESET}")
                return


def _build_compare_sources(prompt_manager_cls, project_root: Path) -> List[tuple]:
    sources: List[tuple] = []
    catalog = prompt_manager_cls.get_prompt_catalog()
    sources.append(("current", catalog.get("system_template", "")))
    sources.append(("built_in_default", prompt_manager_cls.SYSTEM_TEMPLATE))

    for name in prompt_manager_cls.list_prepared_templates():
        payload = prompt_manager_cls.get_prepared_template(name)
        sources.append((f"prepared:{name}", payload.get("system_template", "")))

    profiles = prompt_manager_cls.list_prompt_profiles(root=project_root)
    for profile in profiles:
        p = project_root / "prompts" / "custom_profiles" / f"{profile}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        c = d.get("catalog", d)
        sources.append((f"profile:{profile}", c.get("system_template", "")))
    return sources


def _opening_columns_for_terminal() -> int:
    try:
        width = os.get_terminal_size().columns
    except OSError:
        width = 120
    if width >= 220:
        return 6
    if width >= 170:
        return 4
    if width >= 130:
        return 3
    return 2


def _initial_board_state() -> List[List[str]]:
    return [
        list("rnbqkbnr"),
        list("pppppppp"),
        list("........"),
        list("........"),
        list("........"),
        list("........"),
        list("PPPPPPPP"),
        list("RNBQKBNR"),
    ]


def _sq_to_rc(square: str) -> Tuple[int, int]:
    col = ord(square[0]) - ord("a")
    row = 8 - int(square[1])
    return row, col


def _rc_to_sq(row: int, col: int) -> str:
    return f"{chr(ord('a') + col)}{8 - row}"


def _piece_color(piece: str) -> str:
    if piece == ".":
        return ""
    return "w" if piece.isupper() else "b"


def _path_clear(board: List[List[str]], r1: int, c1: int, r2: int, c2: int) -> bool:
    dr = (r2 - r1)
    dc = (c2 - c1)
    step_r = 0 if dr == 0 else (1 if dr > 0 else -1)
    step_c = 0 if dc == 0 else (1 if dc > 0 else -1)
    cr, cc = r1 + step_r, c1 + step_c
    while (cr, cc) != (r2, c2):
        if board[cr][cc] != ".":
            return False
        cr += step_r
        cc += step_c
    return True


def _can_piece_reach(board: List[List[str]], piece: str, fr: int, fc: int, tr: int, tc: int) -> bool:
    pr = piece.upper()
    dr, dc = tr - fr, tc - fc
    adr, adc = abs(dr), abs(dc)
    if pr == "N":
        return (adr, adc) in {(1, 2), (2, 1)}
    if pr == "K":
        return max(adr, adc) == 1
    if pr == "B":
        return adr == adc and _path_clear(board, fr, fc, tr, tc)
    if pr == "R":
        return (dr == 0 or dc == 0) and _path_clear(board, fr, fc, tr, tc)
    if pr == "Q":
        return (adr == adc or dr == 0 or dc == 0) and _path_clear(board, fr, fc, tr, tc)
    return False


def _clean_san(san: str) -> str:
    m = san.strip()
    m = m.replace("0-0-0", "O-O-O").replace("0-0", "O-O")
    m = m.replace("e.p.", "").strip()
    return re.sub(r"[+#?!]+$", "", m)


def _apply_san_move(board: List[List[str]], san: str, side: str) -> Tuple[bool, str]:
    move = _clean_san(san)
    if not move:
        return False, "empty move"

    if move in ("O-O", "O-O-O"):
        if side == "w":
            king_from, rook_from = ("e1", "h1") if move == "O-O" else ("e1", "a1")
            king_to, rook_to = ("g1", "f1") if move == "O-O" else ("c1", "d1")
        else:
            king_from, rook_from = ("e8", "h8") if move == "O-O" else ("e8", "a8")
            king_to, rook_to = ("g8", "f8") if move == "O-O" else ("c8", "d8")
        kfr, kfc = _sq_to_rc(king_from)
        rfr, rfc = _sq_to_rc(rook_from)
        ktr, ktc = _sq_to_rc(king_to)
        rtr, rtc = _sq_to_rc(rook_to)
        board[ktr][ktc], board[kfr][kfc] = board[kfr][kfc], "."
        board[rtr][rtc], board[rfr][rfc] = board[rfr][rfc], "."
        return True, ""

    pawn_cap = re.fullmatch(r"([a-h])x([a-h][1-8])(=([QRBN]))?", move)
    pawn_quiet = re.fullmatch(r"([a-h][1-8])(=([QRBN]))?", move)
    piece_move = re.fullmatch(r"([KQRBN])([a-h1-8]{0,2})x?([a-h][1-8])", move)

    if pawn_cap:
        from_file, to_sq = pawn_cap.group(1), pawn_cap.group(2)
        promo = pawn_cap.group(4)
        tr, tc = _sq_to_rc(to_sq)
        dirn = -1 if side == "w" else 1
        fr = tr - dirn
        fc = ord(from_file) - ord("a")
        if not (0 <= fr < 8 and 0 <= fc < 8):
            return False, f"invalid pawn capture {move}"
        piece = board[fr][fc]
        expect = "P" if side == "w" else "p"
        if piece != expect:
            return False, f"pawn source not found for {move}"
        board[fr][fc] = "."
        board[tr][tc] = (promo or "P").upper() if side == "w" else (promo or "p").lower()
        return True, ""

    if pawn_quiet and move[0].islower():
        to_sq = pawn_quiet.group(1)
        promo = pawn_quiet.group(3)
        tr, tc = _sq_to_rc(to_sq)
        expect = "P" if side == "w" else "p"
        step = 1 if side == "w" else -1
        start_row = 6 if side == "w" else 1
        fr1 = tr + step
        if 0 <= fr1 < 8 and board[fr1][tc] == expect and board[tr][tc] == ".":
            board[fr1][tc] = "."
            board[tr][tc] = (promo or "P").upper() if side == "w" else (promo or "p").lower()
            return True, ""
        fr2 = tr + 2 * step
        mid = tr + step
        if (
            0 <= fr2 < 8
            and fr2 == start_row
            and board[fr2][tc] == expect
            and board[mid][tc] == "."
            and board[tr][tc] == "."
        ):
            board[fr2][tc] = "."
            board[tr][tc] = expect
            return True, ""
        return False, f"pawn push not found for {move}"

    if piece_move:
        p, dis, to_sq = piece_move.group(1), piece_move.group(2), piece_move.group(3)
        tr, tc = _sq_to_rc(to_sq)
        want = p if side == "w" else p.lower()
        candidates: List[Tuple[int, int]] = []
        for r in range(8):
            for c in range(8):
                if board[r][c] != want:
                    continue
                if dis:
                    if len(dis) == 2:
                        if _rc_to_sq(r, c) != dis:
                            continue
                    elif dis.isdigit():
                        if str(8 - r) != dis:
                            continue
                    elif dis.isalpha():
                        if chr(ord("a") + c) != dis:
                            continue
                if _can_piece_reach(board, want, r, c, tr, tc):
                    dst = board[tr][tc]
                    if dst == "." or _piece_color(dst) != side:
                        candidates.append((r, c))
        if not candidates:
            return False, f"piece source not found for {move}"
        fr, fc = candidates[0]
        board[fr][fc] = "."
        board[tr][tc] = want
        return True, ""

    return False, f"unsupported SAN: {move}"


def _render_ascii_board(board: List[List[str]], *, io: dict) -> str:
    C = io["C"]
    piece_icons: Dict[str, str] = {
        "K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
        "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟",
        ".": " ",
    }
    use_icons = os.isatty(1)
    use_color = os.isatty(1) and bool(C.RESET)
    try:
        term_w = os.get_terminal_size().columns
    except OSError:
        term_w = 120
    ultra = term_w >= 220
    wide = term_w >= 170
    cell_w = 7 if ultra else (5 if wide else 3)
    double_rows = ultra
    white_fg = "\033[97m"
    black_fg = "\033[96m"
    coord_fg = C.CYAN if use_color else ""
    border_fg = C.DIM if use_color else ""
    dark_sq_fg = "\033[90m" if use_color else ""
    light_sq_fg = "\033[37m" if use_color else ""
    reset = C.RESET if use_color else ""

    def _file_line() -> str:
        chunks = [f"{f:^{cell_w}}" for f in "abcdefgh"]
        return f"      {coord_fg}{' '.join(chunks)}{reset}"

    h = "─" * cell_w
    top = f"    {border_fg}┌" + "┬".join([h] * 8) + f"┐{reset}"
    mid = f"    {border_fg}├" + "┼".join([h] * 8) + f"┤{reset}"
    bottom = f"    {border_fg}└" + "┴".join([h] * 8) + f"┘{reset}"
    files = _file_line()
    lines = [files, top]

    def _center_cell(piece: str, row: int, col: int, with_piece: bool) -> str:
        if not with_piece:
            sq = "·" if (row + col) % 2 else " "
            if use_color:
                tone = dark_sq_fg if (row + col) % 2 else light_sq_fg
                s = f"{tone}{sq}{reset}"
            else:
                s = sq
        else:
            symbol = piece_icons.get(piece, piece) if use_icons else (" " if piece == "." else piece)
            if piece == ".":
                sq = "·" if (row + col) % 2 else " "
                if use_color:
                    tone = dark_sq_fg if (row + col) % 2 else light_sq_fg
                    s = f"{tone}{sq}{reset}"
                else:
                    s = sq
            else:
                if use_color:
                    fg = white_fg if piece.isupper() else black_fg
                    s = f"{fg}{symbol}{reset}"
                else:
                    s = symbol
        left = (cell_w - 1) // 2
        right = cell_w - 1 - left
        return (" " * left) + s + (" " * right)

    for r in range(8):
        rank = 8 - r
        cells_piece = [_center_cell(board[r][c], r, c, with_piece=True) for c in range(8)]
        lines.append(
            f"  {coord_fg}{rank}{reset} {border_fg}│{reset}"
            + f"{border_fg}│{reset}".join(cells_piece)
            + f"{border_fg}│{reset} {coord_fg}{rank}{reset}"
        )
        if double_rows:
            cells_texture = [_center_cell(board[r][c], r, c, with_piece=False) for c in range(8)]
            lines.append(
                f"    {border_fg}│{reset}"
                + f"{border_fg}│{reset}".join(cells_texture)
                + f"{border_fg}│{reset}"
            )
        lines.append(mid if r < 7 else bottom)
    lines.append(files)
    return "\n".join(lines)


def _opening_board_preview(moves: List[str], *, io: dict) -> Tuple[str, Optional[str], int]:
    board = _initial_board_state()
    side = "w"
    applied = 0
    error: Optional[str] = None
    for mv in moves:
        ok, err = _apply_san_move(board, mv, side)
        if not ok:
            error = err
            break
        side = "b" if side == "w" else "w"
        applied += 1
    return _render_ascii_board(board, io=io), error, applied


def _opening_browser(prompt_manager_cls, *, io: dict):
    C = io["C"]
    UI = io["UI"]
    GO_BACK = io["GO_BACK"]
    project_root = io["project_root"]
    prompt_yes_no = io["prompt_yes_no"]
    print_warning = io["print_warning"]
    print_success = io["print_success"]
    print_error = io["print_error"]
    print_info = io["print_info"]
    _soft_rule = io["soft_rule"]

    all_keys = prompt_manager_cls.list_opening_keys(root=project_root)
    if not all_keys:
        print_warning("No openings available.")
        return GO_BACK

    filtered = list(all_keys)
    page = 0
    page_size = 48
    columns = _opening_columns_for_terminal()
    query = ""
    sort_mode = "key"
    gap = 2
    animations = True
    theme = "vivid"

    def _animate_tick(label: str = "Updating view"):
        if not animations:
            return
        frames = ("⠋", "⠙", "⠸")
        for f in frames:
            print(f"\r  {C.CYAN}{f}{C.RESET} {label}...", end="", flush=True)
            time.sleep(0.04)
        print("\r" + " " * 48 + "\r", end="", flush=True)

    def _style_key(index: int, key: str, max_key_chars: int) -> str:
        fav = set(prompt_manager_cls.get_opening_favorites())
        rec = set(prompt_manager_cls.get_opening_recents()[:10])
        marker = " "
        color = C.WHITE if theme == "vivid" else C.RESET
        if key in fav:
            marker = "★"
            color = C.YELLOW
        elif key in rec:
            marker = "●"
            color = C.CYAN
        if query and query in key.lower():
            color = C.MAGENTA if theme == "vivid" else color
        clipped = key if len(key) <= max_key_chars else key[:max(1, max_key_chars - 1)] + "…"
        return f"{color}{index:>3}. {marker} {clipped}{C.RESET}"

    def _rebuild_filtered():
        nonlocal filtered
        q = query.strip().lower()
        if not q:
            filtered = list(all_keys)
        elif q.startswith("eco:"):
            target = q[4:].strip().upper()
            filtered = [k for k in all_keys if prompt_manager_cls.get_opening_pack(k, root=project_root).get("eco", "").upper() == target]
        elif q.startswith("prefix:"):
            target = q[7:].strip().lower()
            filtered = [k for k in all_keys if k.lower().startswith(target)]
        else:
            tokens = [t for t in q.split() if t]
            filtered = [k for k in all_keys if all(tok in k.lower() for tok in tokens)]

        if sort_mode == "eco":
            filtered.sort(key=lambda k: (prompt_manager_cls.get_opening_pack(k, root=project_root).get("eco", ""), k))
        elif sort_mode == "len":
            filtered.sort(key=lambda k: (len(k), k))
        elif sort_mode == "recent":
            rec = prompt_manager_cls.get_opening_recents()
            rank = {k: i for i, k in enumerate(rec)}
            filtered.sort(key=lambda k: (rank.get(k, 9999), k))
        elif sort_mode == "fav":
            fav = set(prompt_manager_cls.get_opening_favorites())
            filtered.sort(key=lambda k: (0 if k in fav else 1, k))
        else:
            filtered.sort()

    _rebuild_filtered()

    while True:
        total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
        page = max(0, min(page, total_pages - 1))
        start = page * page_size
        chunk = filtered[start:start + page_size]

        _soft_rule()
        print(f"  {C.BOLD}{C.CYAN}Opening Browser{C.RESET}  {C.DIM}({theme}, animations {'on' if animations else 'off'}){C.RESET}")
        fresh_count = prompt_manager_cls.fresh_openings_count(root=project_root)
        count_color = C.GREEN if fresh_count == len(all_keys) else C.YELLOW
        print(
            f"  {C.DIM}Total openings: {count_color}{len(all_keys)}{C.DIM} | Fresh file: {fresh_count} | Showing: {len(filtered)} | "
            f"Page: {C.CYAN}{page + 1}{C.DIM}/{total_pages} | Cols: {columns} | Sort: {sort_mode} | Query: {query or '(none)'}{C.RESET}"
        )
        print(f"  {C.DIM}Source: {prompt_manager_cls.openings_source_path(root=project_root)}{C.RESET}")

        if not chunk:
            print_warning("No openings match current filter.")
        else:
            try:
                term_w = os.get_terminal_size().columns
            except OSError:
                term_w = 160
            col_width = max(18, (term_w - 4 - (columns - 1) * gap) // columns)
            for r in range((len(chunk) + columns - 1) // columns):
                cells = []
                for c in range(columns):
                    idx = r + c * ((len(chunk) + columns - 1) // columns)
                    if idx < len(chunk):
                        abs_idx = start + idx + 1
                        key_room = max(6, col_width - 7)
                        label = _style_key(abs_idx, chunk[idx], key_room)
                        printable = re.sub(r"\x1b\[[0-9;]*m", "", label)
                        pad = max(0, col_width - len(printable))
                        cells.append(label + (" " * pad))
                print("  " + (" " * gap).join(cells))

        print(f"\n  {C.DIM}Commands:{C.RESET}")
        print("   • number = select opening")
        print("   • i <number> = inspect opening details, board preview, and quick-select")
        print("   • /text = filter (supports: eco:B33, prefix:sicilian_, multi-word)")
        print("   • verify = compare cached count vs fresh file read")
        print("   • g <page> / j <index> = jump")
        print("   • sort key|eco|len|recent|fav = sort mode")
        print("   • fav <number> = toggle favorite")
        print("   • recents = show recent selections")
        print("   • n / p = next / previous page")
        print("   • c = cycle columns (2/3/4/6), gap <n> = column spacing")
        print("   • anim on|off, theme vivid|classic")
        print("   • r = reload openings from disk")
        print("   • all = clear filter")
        print("   • 0 = back")

        raw = input(f"\n  {C.YELLOW}{UI['prompt']}{C.RESET} Choose opening or command: ").strip()
        if raw.lower() in ("0", "back", "b"):
            return GO_BACK
        if raw.lower() == "n":
            _animate_tick("Loading next page")
            page += 1
            continue
        if raw.lower() == "p":
            _animate_tick("Loading previous page")
            page -= 1
            continue
        if raw.lower() == "verify":
            cached = len(all_keys)
            fresh = prompt_manager_cls.fresh_openings_count(root=project_root)
            if cached == fresh:
                print_success(f"Opening count verified: {cached}")
            else:
                print_warning(f"Count mismatch: cached={cached}, fresh={fresh}. Use 'r' to reload.")
            continue
        if raw.lower().startswith("g "):
            try:
                tgt = int(raw.split(maxsplit=1)[1])
                _animate_tick("Jumping")
                page = max(0, min(tgt - 1, max(0, total_pages - 1)))
            except Exception:
                print_error("Invalid page command. Use: g <page>")
            continue
        if raw.lower().startswith("j "):
            try:
                tgt = int(raw.split(maxsplit=1)[1])
                if 1 <= tgt <= len(filtered):
                    return filtered[tgt - 1]
                print_error(f"Index out of range 1-{len(filtered)}.")
            except Exception:
                print_error("Invalid jump command. Use: j <index>")
            continue
        if raw.lower().startswith("gap "):
            try:
                gap = max(1, min(6, int(raw.split(maxsplit=1)[1])))
            except Exception:
                print_error("Invalid gap command. Use: gap <1-6>")
            continue
        if raw.lower().startswith("anim "):
            v = raw.split(maxsplit=1)[1].strip().lower()
            if v in ("on", "off"):
                animations = (v == "on")
                print_success(f"Animations {'enabled' if animations else 'disabled'}.")
            else:
                print_error("Use: anim on|off")
            continue
        if raw.lower().startswith("theme "):
            v = raw.split(maxsplit=1)[1].strip().lower()
            if v in ("vivid", "classic"):
                theme = v
                print_success(f"Theme set to {theme}.")
            else:
                print_error("Use: theme vivid|classic")
            continue
        if raw.lower() == "recents":
            rec = prompt_manager_cls.get_opening_recents()
            if not rec:
                print_info("No recent openings yet.")
            else:
                print_info("Recent openings:")
                for i, k in enumerate(rec, 1):
                    print(f"   {i:>2}. {k}")
            continue
        if raw.lower().startswith("sort "):
            m = raw.split(maxsplit=1)[1].strip().lower()
            if m in ("key", "eco", "len", "recent", "fav"):
                sort_mode = m
                _rebuild_filtered()
                page = 0
            else:
                print_error("Sort modes: key|eco|len|recent|fav")
            continue
        if raw.lower().startswith("fav "):
            try:
                num = int(raw.split(maxsplit=1)[1])
                if not (1 <= num <= len(filtered)):
                    raise ValueError
                key = filtered[num - 1]
                is_fav = prompt_manager_cls.toggle_opening_favorite(key)
                print_success(f"{'Added to' if is_fav else 'Removed from'} favorites: {key}")
                _rebuild_filtered()
            except Exception:
                print_error("Invalid favorite command. Use: fav <number>")
            continue
        if raw.lower() == "c":
            columns = {2: 3, 3: 4, 4: 6, 6: 2}[columns]
            continue
        if raw.lower() == "r":
            _animate_tick("Reloading openings")
            count = prompt_manager_cls.reload_openings(root=project_root)
            all_keys = prompt_manager_cls.list_opening_keys(root=project_root)
            _rebuild_filtered()
            page = 0
            print_success(f"Reloaded openings from disk. Count={count}")
            continue
        if raw.lower() == "all":
            query = ""
            _rebuild_filtered()
            page = 0
            continue
        if raw.startswith("/"):
            _animate_tick("Filtering")
            query = raw[1:].strip().lower()
            _rebuild_filtered()
            page = 0
            continue
        if raw.lower().startswith("i "):
            try:
                num = int(raw.split(maxsplit=1)[1])
                if not (1 <= num <= len(filtered)):
                    raise ValueError
                key = filtered[num - 1]
                item = prompt_manager_cls.get_opening_pack(key, root=project_root)
                print(f"\n  {C.BOLD}{key}{C.RESET}")
                print(f"   ECO:   {item.get('eco', 'N/A')}")
                print(f"   Moves: {' '.join(item.get('moves', []))}")
                print(f"   Notes: {item.get('notes', '')}")
                board_text, board_err, applied = _opening_board_preview(item.get("moves", []), io=io)
                print()
                _soft_rule()
                print(f"\n  {C.CYAN}{C.BOLD}Board preview after opening line ({applied}/{len(item.get('moves', []))} plies):{C.RESET}")
                print(board_text)
                _soft_rule()
                if board_err:
                    print_warning(f"Board preview stopped early: {board_err}")
                q = prompt_yes_no("Select this opening?", default=False, allow_back=True)
                if q is not GO_BACK and q:
                    return key
            except Exception:
                print_error("Invalid inspect command. Use: i <number>")
            continue
        try:
            num = int(raw)
            if 1 <= num <= len(filtered):
                key = filtered[num - 1]
                prompt_manager_cls.track_opening_recent(key)
                return key
            print_error(f"Enter a number between 1 and {len(filtered)}.")
        except ValueError:
            print_error("Unknown command.")


def interactive_prompt_studio(*, io: dict):
    from core.prompt_manager import PromptManager, GameContext, GameEra, PromptBias

    C = io["C"]
    GO_BACK = io["GO_BACK"]
    project_root = io["project_root"]
    prompt_choice = io["prompt_choice"]
    prompt_input = io["prompt_input"]
    prompt_int = io["prompt_int"]
    prompt_yes_no = io["prompt_yes_no"]
    print_header = io["print_header"]
    print_info = io["print_info"]
    print_warning = io["print_warning"]
    print_error = io["print_error"]
    print_success = io["print_success"]
    read_multiline_input = io["read_multiline_input"]

    print()
    print_header("Prompt Studio")
    strict_mode = True
    while True:
        state = PromptManager.get_prompt_context_state()
        options = [
            "Catalog & status",
            "Template library",
            "Edit session prompts",
            "Compare prompts",
            "Context simulator",
            "Profiles",
            f"Toggle validation mode (current: {'strict' if strict_mode else 'warn-only'})",
            "Clear session overrides",
            "Back",
        ]
        print_info(
            f"Context: mode={state.get('mode','single')} | opening={state.get('opening_key') or 'none'} | "
            f"commentary={state.get('commentary_profile','off')}({state.get('commentary_intensity','5')}/10)"
        )
        choice = prompt_choice("Prompt Studio sections:", options, default=1, allow_back=True)
        if choice is GO_BACK:
            break

        if choice == 0:
            catalog = PromptManager.get_prompt_catalog()
            print_info("Active prompt catalog:")
            for key, val in catalog.items():
                print(f"\n  {C.BOLD}{key}{C.RESET}\n{C.DIM}{'-' * 60}{C.RESET}")
                lines = (val or "").splitlines()
                for line in lines[:24]:
                    print(f"  {line}")
                if len(lines) > 24:
                    print(f"  {C.DIM}... ({len(lines)-24} more lines){C.RESET}")

        elif choice == 1:
            templates = PromptManager.list_prepared_templates()
            idx = prompt_choice("Select prepared template:", templates, default=1, allow_back=True)
            if idx is GO_BACK:
                continue
            selected_name = templates[idx]
            selected = PromptManager.get_prepared_template(selected_name)
            preview_choice = prompt_choice("Preview length:", ["16 lines", "40 lines", "Full"], default=1, allow_back=True)
            if preview_choice is GO_BACK:
                continue
            line_count = 16 if preview_choice == 0 else 40 if preview_choice == 1 else -1
            _preview_template(selected_name, selected, preview_lines=line_count, io=io)
            apply_idx = prompt_choice("Apply this template?", ["Apply template", "Back"], default=2, allow_back=True)
            if apply_idx is GO_BACK or apply_idx == 1:
                continue
            report = PromptManager.lint_system_template(selected["system_template"])
            for warn in report["warnings"]:
                print_warning(warn)
            print_info(f"Risk score: {report.get('risk_score', 0)}/100 ({report.get('risk_level', 'low')})")
            for f in report.get("risk_findings", [])[:6]:
                print_info(f"Risk factor: {f}")
            if strict_mode and report["strict_errors"]:
                for err in report["strict_errors"]:
                    print_error(err)
                print_warning("Strict mode: template not applied.")
                continue
            PromptManager.set_prompt_overrides(
                system_template=selected.get("system_template"),
                user_prompt_prefix=selected.get("user_prompt_prefix"),
                user_prompt_suffix=selected.get("user_prompt_suffix"),
            )
            print_success(f"Prepared template '{selected_name}' applied.")

        elif choice == 2:
            edit_choice = prompt_choice(
                "Edit session prompts:",
                ["Set system template", "Set user prefix", "Set user suffix", "Dry-run compile preview", "Back"],
                default=1,
                allow_back=True,
            )
            if edit_choice is GO_BACK or edit_choice == 4:
                continue
            if edit_choice == 0:
                input_mode = prompt_choice(
                    "System template input mode:",
                    ["Single-line input", "Multiline paste (EOF)"],
                    default=2,
                    allow_back=True,
                )
                if input_mode is GO_BACK:
                    continue
                if input_mode == 0:
                    text = prompt_input("Paste new SYSTEM template (single-line/pasted text)", "", allow_back=True)
                    if text is GO_BACK:
                        continue
                else:
                    text = read_multiline_input("Enter SYSTEM template")
                    if not text:
                        print_warning("No content entered.")
                        continue
                import difflib

                old_lines = (PromptManager.get_prompt_catalog().get("system_template") or "").splitlines()
                preview = list(difflib.unified_diff(old_lines, text.splitlines(), fromfile="current", tofile="candidate", lineterm=""))
                if preview:
                    print_info("Template diff preview:")
                    for line in preview[:120]:
                        color = C.GREEN if line.startswith("+") and not line.startswith("+++") else C.RED if line.startswith("-") and not line.startswith("---") else C.DIM
                        print(f"{color}{line}{C.RESET}")
                mode_for_lint = PromptManager.get_prompt_context_state().get("mode", "single")
                report = PromptManager.lint_template_with_mode(text, mode_for_lint)
                for warn in report["warnings"]:
                    print_warning(warn)
                print_info(f"Risk score: {report.get('risk_score', 0)}/100 ({report.get('risk_level', 'low')})")
                for f in report.get("risk_findings", [])[:6]:
                    print_info(f"Risk factor: {f}")
                badges = PromptManager.compatibility_badges(text)
                print_info(f"Compatibility: single {'✅' if badges['single'] else '⚠'} | match {'✅' if badges['match'] else '⚠'} | tournament {'✅' if badges['tournament'] else '⚠'}")
                if strict_mode and report["strict_errors"]:
                    for err in report["strict_errors"]:
                        print_error(err)
                    print_warning("Strict mode: override not applied.")
                    continue
                PromptManager.set_prompt_overrides(system_template=text)
                print_success("Session system template override set.")
            elif edit_choice == 1:
                text = prompt_input("Enter user prompt prefix", "", allow_back=True)
                if text is not GO_BACK:
                    PromptManager.set_prompt_overrides(user_prompt_prefix=text)
                    print_success("Session user prompt prefix set.")
            elif edit_choice == 2:
                text = prompt_input("Enter user prompt suffix", "", allow_back=True)
                if text is not GO_BACK:
                    PromptManager.set_prompt_overrides(user_prompt_suffix=text)
                    print_success("Session user prompt suffix set.")
            else:
                pm = PromptManager()
                sample = GameContext(
                    era=GameEra.ROMANTIC, theme=None, white_player="Caissa White", black_player="Caissa Black",
                    aggression_score=7, chaos_score=5, depth=40, bias=PromptBias.NEUTRAL,
                )
                s = pm.build_system_prompt(sample)
                u = pm.build_user_prompt(sample)
                preview_mode = prompt_choice(
                    "Dry-run preview length:",
                    ["30/20 lines", "60/40 lines", "Full"],
                    default=1,
                    allow_back=True,
                )
                if preview_mode is GO_BACK:
                    continue
                sys_lines = 30 if preview_mode == 0 else 60 if preview_mode == 1 else -1
                usr_lines = 20 if preview_mode == 0 else 40 if preview_mode == 1 else -1
                print_info("Dry-run compile preview:")
                print(f"  System prompt chars: {len(s)}")
                print(f"  User prompt chars:   {len(u)}")
                print(f"  Estimated tokens:    ~{(len(s)+len(u))//4}")
                print(f"\n  {C.BOLD}System Prompt ({'full' if sys_lines < 0 else f'first {sys_lines} lines'}){C.RESET}")
                s_lines = s.splitlines()
                for line in (s_lines if sys_lines < 0 else s_lines[:sys_lines]):
                    print(f"  {line}")
                print(f"\n  {C.BOLD}User Prompt ({'full' if usr_lines < 0 else f'first {usr_lines} lines'}){C.RESET}")
                u_lines = u.splitlines()
                for line in (u_lines if usr_lines < 0 else u_lines[:usr_lines]):
                    print(f"  {line}")

        elif choice == 3:
            sources = _build_compare_sources(PromptManager, project_root)
            labels = [label for label, _ in sources]
            if len(labels) < 2:
                print_warning("Not enough sources to compare.")
                continue
            i1 = prompt_choice("Select source A:", labels, default=1, allow_back=True)
            if i1 is GO_BACK:
                continue
            i2 = prompt_choice("Select source B:", labels, default=2 if len(labels) > 1 else 1, allow_back=True)
            if i2 is GO_BACK:
                continue
            if i1 == i2:
                print_warning("Source A and B are identical selections.")
                continue
            vm = prompt_choice("Comparison view:", ["Side-by-side", "Unified diff", "Summary only"], default=1, allow_back=True)
            if vm is GO_BACK:
                continue
            view_mode = "side_by_side" if vm == 0 else "unified" if vm == 1 else "summary"
            name_a, t1 = sources[i1]
            name_b, t2 = sources[i2]
            _print_system_template_comparison(name_a, t1, name_b, t2, view_mode=view_mode, io=io)

        elif choice == 4:
            ctx_action = prompt_choice(
                "Context simulator:",
                [
                    "Set mode contract",
                    "Set opening pack (from openings.json)",
                    "Set commentary profile/knobs",
                    "Clear opening pack",
                    "Simulate effective prompts",
                    "Back",
                ],
                default=1,
                allow_back=True,
            )
            if ctx_action is GO_BACK or ctx_action == 5:
                continue
            if ctx_action == 0:
                m = prompt_choice("Select mode:", ["single", "match", "tournament"], default=1, allow_back=True)
                if m is GO_BACK:
                    continue
                PromptManager.set_prompt_mode(["single", "match", "tournament"][m])
                print_success(f"Prompt mode set to: {['single','match','tournament'][m]}")
            elif ctx_action == 1:
                selected_key = _opening_browser(PromptManager, io=io)
                if selected_key is GO_BACK:
                    continue
                PromptManager.set_opening_override(selected_key)
                pack = PromptManager.get_opening_pack(selected_key, root=project_root)
                print_success(f"Opening pack set: {selected_key} (ECO {pack.get('eco','N/A')})")
            elif ctx_action == 2:
                p = prompt_choice("Commentary profile:", ["off", "broadcast", "educational", "dramatic"], default=1, allow_back=True)
                if p is GO_BACK:
                    continue
                intensity = prompt_int("Commentary intensity (0-10)", 5, min_val=0, max_val=10)
                if intensity is GO_BACK:
                    continue
                selected_profile = ["off", "broadcast", "educational", "dramatic"][p]
                preview = PromptManager.preview_commentary_injection(selected_profile, intensity)
                print(f"\n  {C.BOLD}Commentary injection preview{C.RESET}")
                print(f"  {C.DIM}{'-' * 60}{C.RESET}")
                for line in str(preview).splitlines():
                    print(f"  {line}")
                apply_preview = prompt_choice("Apply this commentary profile?", ["Apply", "Back"], default=1, allow_back=True)
                if apply_preview is GO_BACK or apply_preview == 1:
                    continue
                PromptManager.set_commentary_profile(selected_profile, intensity=intensity)
                print_success("Commentary profile updated.")
            elif ctx_action == 3:
                PromptManager.set_opening_override(None)
                print_success("Opening pack cleared.")
            else:
                st = PromptManager.get_prompt_context_state()
                sim = PromptManager.simulate_prompt_context(
                    mode=st.get("mode", "single"),
                    opening_key=st.get("opening_key") or None,
                )
                print_info(
                    f"Simulated context: mode={sim['mode']} opening={sim['opening_key'] or 'none'} "
                    f"commentary={sim.get('commentary_profile','off')}({sim.get('commentary_intensity',5)}/10) "
                    f"chars(system/user)=({sim['system_chars']}/{sim['user_chars']}) "
                    f"tokens~{sim['token_estimate']}"
                )
                pv = prompt_choice("Preview length:", ["30/20 lines", "60/40 lines", "Full"], default=1, allow_back=True)
                if pv is GO_BACK:
                    continue
                sys_lines = 30 if pv == 0 else 60 if pv == 1 else -1
                usr_lines = 20 if pv == 0 else 40 if pv == 1 else -1
                print(f"\n  {C.BOLD}System Prompt ({'full' if sys_lines < 0 else f'first {sys_lines} lines'}){C.RESET}")
                s_lines = sim["system_prompt"].splitlines()
                for line in (s_lines if sys_lines < 0 else s_lines[:sys_lines]):
                    print(f"  {line}")
                print(f"\n  {C.BOLD}User Prompt ({'full' if usr_lines < 0 else f'first {usr_lines} lines'}){C.RESET}")
                u_lines = sim["user_prompt"].splitlines()
                for line in (u_lines if usr_lines < 0 else u_lines[:usr_lines]):
                    print(f"  {line}")

        elif choice == 5:
            profile_action = prompt_choice("Profile actions:", ["Save profile", "Load profile", "Back"], default=1, allow_back=True)
            if profile_action is GO_BACK or profile_action == 2:
                continue
            if profile_action == 0:
                name = prompt_input("Profile name", "default_profile", allow_back=True)
                if name is GO_BACK:
                    continue
                author = prompt_input("Author", "caissa-user", allow_back=True)
                if author is GO_BACK:
                    continue
                version = prompt_input("Version", "1.0.0", allow_back=True)
                if version is GO_BACK:
                    continue
                catalog = PromptManager.get_prompt_catalog()
                compatibility = PromptManager.compatibility_badges(catalog["system_template"])
                path = PromptManager.save_prompt_profile(name, root=project_root, author=author, version=version, compatibility=compatibility)
                print_success(f"Saved profile: {path}")
            else:
                profiles = PromptManager.list_prompt_profiles(root=project_root)
                if not profiles:
                    print_warning("No prompt profiles found.")
                    continue
                idx = prompt_choice("Select profile to load:", profiles, default=1, allow_back=True)
                if idx is GO_BACK:
                    continue
                path = PromptManager.load_prompt_profile(profiles[idx], root=project_root)
                meta = PromptManager.read_prompt_profile_metadata(profiles[idx], root=project_root)
                if meta:
                    print_info(f"Profile metadata: author={meta.get('author','n/a')} version={meta.get('version','n/a')} checksum={meta.get('checksum','n/a')}")
                print_success(f"Loaded profile: {path}")

        elif choice == 6:
            strict_mode = not strict_mode
            print_info(f"Validation mode set to: {'strict' if strict_mode else 'warn-only'}")

        elif choice == 7:
            PromptManager.clear_prompt_overrides()
            print_success("Session overrides cleared.")

        else:
            break

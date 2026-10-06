"""Bounded, deterministic read-only search over validated project snapshots.

Text, paths, symbols, and returned snippets are untrusted data. Queries use
literal matching only; source text is never parsed or executed in this module.
"""

from __future__ import annotations

import time
from array import array
from collections.abc import Iterator, Sequence

from ..permissions import PermissionLevel
from ..workspace import Workspace
from . import runtime
from .errors import CodingLimitError
from .interfaces import CodingOperation
from .limits import CodingLimits
from .models import (
    MAX_CODING_SEARCH_CONTEXT_CHARS,
    CodeAnalysisResult,
    CodeSearchLimitReason,
    CodeSearchMatch,
    CodeSearchMode,
    CodeSearchRequest,
    CodeSearchResult,
    CodeSymbol,
    CodingProject,
)


class CodeSearchRuntime:
    """Search eligible project files without changing or executing them."""

    name: str = CodingOperation.SEARCH.value
    permission_level: PermissionLevel = CodingOperation.SEARCH.required_permission

    def __init__(self, workspace: Workspace, limits: CodingLimits | None = None) -> None:
        self._workspace = workspace
        self._limits = limits or CodingLimits()
        self._analysis_runtime = runtime.CodingAnalysisRuntime(workspace, self._limits)

    @property
    def limits(self) -> CodingLimits:
        """Return the immutable bounds shared with project analysis."""
        return self._limits

    def search_project(
        self,
        project: CodingProject,
        request: CodeSearchRequest,
    ) -> CodeSearchResult:
        """Search only the analyzed file set and return bounded literal hits."""
        started = time.perf_counter()
        analysis = self._analysis_runtime.analyze_project(project)
        reasons: list[CodeSearchLimitReason] = []
        matches: list[CodeSearchMatch] = []
        incomplete_diagnostics = {
            "project_boundary_invalid",
            "project_discovery_failed",
            "python_ast_limit",
        }
        if (
            analysis.truncated
            or analysis.skipped_files
            or any(item.code in incomplete_diagnostics for item in analysis.diagnostics)
        ):
            _add_reason(reasons, CodeSearchLimitReason.ANALYSIS_INCOMPLETE)

        if self._deadline_reached(started):
            _add_reason(reasons, CodeSearchLimitReason.TIME_LIMIT)
        elif request.mode is CodeSearchMode.FILE_PATH:
            self._search_paths(project, analysis, request, started, matches, reasons)
        elif request.mode is CodeSearchMode.TEXT:
            self._search_text(project, analysis, request, started, matches, reasons)
        else:
            self._search_symbols(project, analysis, request, started, matches, reasons)

        if self._deadline_reached(started):
            _add_reason(reasons, CodeSearchLimitReason.TIME_LIMIT)
        return self._build_result(project, request, matches, reasons)

    def navigate_to_symbol(
        self,
        project: CodingProject,
        symbol_name: str,
        *,
        case_sensitive: bool = False,
    ) -> CodeSearchResult:
        """Resolve exact symbol-name/qualified-name matches to definition sites."""
        request = CodeSearchRequest(
            mode=CodeSearchMode.DEFINITION,
            query=symbol_name,
            case_sensitive=case_sensitive,
        )
        return self.search_project(project, request)

    def _search_paths(
        self,
        project: CodingProject,
        analysis: CodeAnalysisResult,
        request: CodeSearchRequest,
        started: float,
        matches: list[CodeSearchMatch],
        reasons: list[CodeSearchLimitReason],
    ) -> None:
        remaining_chars = self._limits.max_source_chars
        for analyzed in analysis.analyzed_files:
            if self._deadline_reached(started):
                _add_reason(reasons, CodeSearchLimitReason.TIME_LIMIT)
                return
            occurrence = next(
                _find_occurrences(analyzed.path, request.query, request.case_sensitive),
                None,
            )
            if occurrence is None:
                continue
            source = runtime._read_verified_snapshot(
                self._workspace,
                self._limits,
                project,
                analyzed,
                remaining_chars=remaining_chars,
            )
            if source is None:
                _add_reason(reasons, CodeSearchLimitReason.SOURCE_CHANGED)
                continue
            remaining_chars -= len(source.content)
            start, end = occurrence
            match = CodeSearchMatch(
                path=source.path,
                context=_short_context(source.path, start, end),
            )
            if not self._append_match(matches, match, reasons):
                return

    def _search_text(
        self,
        project: CodingProject,
        analysis: CodeAnalysisResult,
        request: CodeSearchRequest,
        started: float,
        matches: list[CodeSearchMatch],
        reasons: list[CodeSearchLimitReason],
    ) -> None:
        symbols_by_path = _symbols_by_path(analysis.symbols)
        remaining_chars = self._limits.max_source_chars
        for analyzed in analysis.analyzed_files:
            if self._deadline_reached(started):
                _add_reason(reasons, CodeSearchLimitReason.TIME_LIMIT)
                return
            source = runtime._read_verified_snapshot(
                self._workspace,
                self._limits,
                project,
                analyzed,
                remaining_chars=remaining_chars,
            )
            if source is None:
                _add_reason(reasons, CodeSearchLimitReason.SOURCE_CHANGED)
                continue
            remaining_chars -= len(source.content)
            file_symbols = symbols_by_path.get(source.path, ())
            for line_number, line in _iter_source_lines(source.content):
                if self._deadline_reached(started):
                    _add_reason(reasons, CodeSearchLimitReason.TIME_LIMIT)
                    return
                for start, end in _find_occurrences(line, request.query, request.case_sensitive):
                    symbol = _symbol_for_location(file_symbols, line_number)
                    column = _bounded_column(start + 1)
                    match = CodeSearchMatch(
                        path=source.path,
                        line=line_number,
                        column=column,
                        symbol=symbol.name if symbol is not None else None,
                        symbol_kind=symbol.kind if symbol is not None else None,
                        context=_short_context(line, start, end),
                    )
                    if not self._append_match(matches, match, reasons):
                        return

    def _search_symbols(
        self,
        project: CodingProject,
        analysis: CodeAnalysisResult,
        request: CodeSearchRequest,
        started: float,
        matches: list[CodeSearchMatch],
        reasons: list[CodeSearchLimitReason],
    ) -> None:
        exact = request.mode is CodeSearchMode.DEFINITION
        candidates = sorted(
            (
                symbol
                for symbol in analysis.symbols
                if _symbol_matches(symbol, request.query, request.case_sensitive, exact=exact)
            ),
            key=_symbol_sort_key,
        )
        if not candidates:
            return

        requested_paths = {symbol.region.path for symbol in candidates}
        sources: dict[str, str] = {}
        remaining_chars = self._limits.max_source_chars
        for analyzed in analysis.analyzed_files:
            if analyzed.path not in requested_paths:
                continue
            if self._deadline_reached(started):
                _add_reason(reasons, CodeSearchLimitReason.TIME_LIMIT)
                break
            source = runtime._read_verified_snapshot(
                self._workspace,
                self._limits,
                project,
                analyzed,
                remaining_chars=remaining_chars,
            )
            if source is None:
                _add_reason(reasons, CodeSearchLimitReason.SOURCE_CHANGED)
                continue
            sources[source.path] = source.content
            remaining_chars -= len(source.content)

        wanted_lines: dict[str, set[int]] = {}
        for symbol in candidates:
            if symbol.region.path in sources:
                wanted_lines.setdefault(symbol.region.path, set()).add(symbol.region.start_line)
        lines_by_path = {
            path: _selected_lines(content, line_numbers)
            for path, content in sources.items()
            if (line_numbers := wanted_lines.get(path))
        }

        for symbol in candidates:
            if self._deadline_reached(started):
                _add_reason(reasons, CodeSearchLimitReason.TIME_LIMIT)
                return
            line = lines_by_path.get(symbol.region.path, {}).get(symbol.region.start_line)
            if line is None:
                continue
            column = _symbol_column(symbol, line)
            occurrence = next(_find_occurrences(line, symbol.name, True), None)
            context_start = (
                occurrence[0]
                if occurrence is not None
                else max(0, (symbol.region.start_column or 1) - 1)
            )
            context_end = context_start + len(symbol.name)
            match = CodeSearchMatch(
                path=symbol.region.path,
                line=symbol.region.start_line,
                column=column,
                symbol=symbol.name,
                symbol_kind=symbol.kind,
                context=_short_context(line, context_start, context_end),
            )
            if not self._append_match(matches, match, reasons):
                return

    def _append_match(
        self,
        matches: list[CodeSearchMatch],
        match: CodeSearchMatch,
        reasons: list[CodeSearchLimitReason],
    ) -> bool:
        if len(matches) >= self._limits.max_search_results:
            _add_reason(reasons, CodeSearchLimitReason.RESULT_LIMIT)
            return False
        matches.append(match)
        return True

    def _deadline_reached(self, started: float) -> bool:
        return time.perf_counter() - started >= self._limits.max_analysis_time_s

    def _build_result(
        self,
        project: CodingProject,
        request: CodeSearchRequest,
        matches: list[CodeSearchMatch],
        reasons: list[CodeSearchLimitReason],
    ) -> CodeSearchResult:
        def make_result() -> CodeSearchResult:
            return CodeSearchResult(
                project_id=project.project_id,
                mode=request.mode,
                query=request.query,
                matches=tuple(matches),
                truncated=bool(reasons),
                limit_reasons=tuple(reasons),
            )

        result = make_result()
        while len(result.model_dump_json().encode("utf-8")) > self._limits.max_output_bytes:
            if not matches:
                raise CodingLimitError()
            matches.pop()
            _add_reason(reasons, CodeSearchLimitReason.OUTPUT_LIMIT)
            result = make_result()
        self._limits.validate_search_result(result)
        result.validate_workspace(project, self._workspace)
        return result


def _symbols_by_path(symbols: Sequence[CodeSymbol]) -> dict[str, tuple[CodeSymbol, ...]]:
    grouped: dict[str, list[CodeSymbol]] = {}
    for symbol in symbols:
        grouped.setdefault(symbol.region.path, []).append(symbol)
    return {path: tuple(items) for path, items in grouped.items()}


def _symbol_sort_key(symbol: CodeSymbol) -> tuple[str, int, int, str, str, str]:
    region = symbol.region
    return (
        region.path,
        region.start_line,
        region.start_column or 0,
        symbol.qualified_name or "",
        symbol.name,
        symbol.kind.value,
    )


def _symbol_matches(
    symbol: CodeSymbol,
    query: str,
    case_sensitive: bool,
    *,
    exact: bool,
) -> bool:
    values = (symbol.name, symbol.qualified_name)
    for value in values:
        if value is None:
            continue
        candidate = value if case_sensitive else value.casefold()
        needle = query if case_sensitive else query.casefold()
        matched = candidate == needle if exact else needle in candidate
        if matched:
            return True
    return False


def _symbol_for_location(symbols: Sequence[CodeSymbol], line_number: int) -> CodeSymbol | None:
    containing = [
        symbol
        for symbol in symbols
        if symbol.region.start_line <= line_number <= symbol.region.end_line
    ]
    if not containing:
        return None
    return min(
        containing,
        key=lambda symbol: (
            symbol.region.end_line - symbol.region.start_line,
            symbol.region.start_line,
            symbol.qualified_name or "",
            symbol.name,
            symbol.kind.value,
        ),
    )


def _symbol_column(symbol: CodeSymbol, line: str) -> int | None:
    if symbol.region.start_column is not None:
        return _bounded_column(symbol.region.start_column)
    occurrence = next(_find_occurrences(line, symbol.name, True), None)
    if occurrence is None:
        return None
    return _bounded_column(occurrence[0] + 1)


def _bounded_column(column: int) -> int | None:
    return column if 1 <= column <= 16_384 else None


def _iter_source_lines(text: str) -> Iterator[tuple[int, str]]:
    """Yield one-based lines without materializing a source-sized line list."""
    start = 0
    line_number = 1
    index = 0
    while index < len(text):
        char = text[index]
        if char not in "\r\n":
            index += 1
            continue
        yield line_number, text[start:index]
        if char == "\r" and index + 1 < len(text) and text[index + 1] == "\n":
            index += 1
        index += 1
        start = index
        line_number += 1
    if start < len(text) or not text:
        yield line_number, text[start:]


def _selected_lines(text: str, wanted: set[int]) -> dict[int, str]:
    selected: dict[int, str] = {}
    remaining = set(wanted)
    for number, line in _iter_source_lines(text):
        if number in remaining:
            selected[number] = line
            remaining.discard(number)
            if not remaining:
                break
    return selected


def _find_occurrences(
    text: str,
    query: str,
    case_sensitive: bool,
) -> Iterator[tuple[int, int]]:
    folded_to_original: Sequence[int] | None = None
    if case_sensitive:
        haystack = text
        needle = query
    else:
        haystack = text.casefold()
        needle = query.casefold()
        if len(haystack) != len(text):
            index_map = array("I")
            for original_index, char in enumerate(text):
                folded_length = len(char.casefold())
                if folded_length:
                    index_map.extend(array("I", [original_index]) * folded_length)
            folded_to_original = index_map
    if not needle:
        return

    folded_index = 0
    previous_original_index = -1
    while True:
        found = haystack.find(needle, folded_index)
        if found < 0:
            return
        if folded_to_original is None:
            start = found
            end = found + len(needle)
        else:
            if found >= len(folded_to_original):
                return
            start = folded_to_original[found]
            final_index = min(found + len(needle) - 1, len(folded_to_original) - 1)
            end = folded_to_original[final_index] + 1
        if start > previous_original_index:
            yield start, end
            previous_original_index = start
        folded_index = found + 1


def _short_context(text: str, start: int, end: int) -> str:
    if len(text) <= MAX_CODING_SEARCH_CONTEXT_CHARS:
        return text
    content_budget = MAX_CODING_SEARCH_CONTEXT_CHARS - 2
    margin = min(40, content_budget // 4)
    window_start = max(0, start - margin)
    window_start = min(window_start, len(text) - content_budget)
    window_end = min(len(text), window_start + content_budget)
    if end > window_end and end - start < content_budget:
        window_start = min(max(0, end - content_budget + margin), len(text) - content_budget)
        window_end = min(len(text), window_start + content_budget)
    prefix = "…" if window_start > 0 else ""
    suffix = "…" if window_end < len(text) else ""
    return f"{prefix}{text[window_start:window_end]}{suffix}"


def _add_reason(
    reasons: list[CodeSearchLimitReason],
    reason: CodeSearchLimitReason,
) -> None:
    if reason not in reasons:
        reasons.append(reason)

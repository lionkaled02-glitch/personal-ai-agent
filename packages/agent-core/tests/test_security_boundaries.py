"""Phase 2 safety-boundary tests.

Two complementary guards:

1. **Static**: the core source tree must not import or use forbidden
   capabilities (subprocess, shell, raw sockets, network clients, eval/exec,
   dynamic imports).
2. **Behavioral**: the built-in tools must reject injection-style input and
   enforce their bounds; the default tool set must contain no
   HIGH-permission or side-effect tool; the tool runtime must refuse to run
   a tool without an ALLOWED decision.

These tests run fully offline.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from agent_core import (
    CalculatorTool,
    EventBus,
    PermissionDecision,
    ToolInvocation,
    ToolRegistry,
    ToolResult,
    ToolRuntime,
    register_default_tools,
)
from agent_core.errors import PermissionDeniedError
from agent_core.permissions import PermissionLevel
from agent_core.tools import ToolSpec

SRC = Path(__file__).resolve().parents[1] / "src" / "agent_core"

# Modules/capabilities that must never appear in core source. The vendor
# provider SDK (openai, imported lazily in providers/) is deliberately NOT
# on this list: it is the approved, isolated provider layer, not a tool.
FORBIDDEN_MODULES = {
    "subprocess",
    "shutil",
    "ctypes",
    "multiprocessing",
    "socket",
    "http.client",
    "urllib.request",
    "requests",
    "httpx",
}

_IMPORT_RE = re.compile(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_.]*)", re.MULTILINE)


class TestStaticSourceBoundaries:
    @pytest.mark.parametrize("module", sorted(FORBIDDEN_MODULES))
    def test_forbidden_module_not_imported(self, module: str) -> None:
        offenders = []
        for path in sorted(SRC.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            for match in _IMPORT_RE.finditer(source):
                imported = match.group(1)
                if imported == module or imported.startswith(module + "."):
                    offenders.append(f"{path.name}: {imported}")
        assert offenders == [], f"forbidden import {module!r} found in: {offenders}"

    def test_no_eval_or_exec_calls(self) -> None:
        offenders = []
        for path in sorted(SRC.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            for pattern in (r"\beval\s*\(", r"\bexec\s*\(", r"__import__\s*\("):
                if re.search(pattern, source):
                    offenders.append(f"{path.name}: {pattern}")
        assert offenders == []

    def test_no_shell_invocations(self) -> None:
        offenders = []
        for path in sorted(SRC.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            for pattern in (r"os\.system\s*\(", r"os\.popen\s*\(", r"shell\s*=\s*True"):
                if re.search(pattern, source):
                    offenders.append(f"{path.name}: {pattern}")
        assert offenders == []


class TestCalculatorInjections:
    tool = CalculatorTool()

    @pytest.mark.parametrize(
        "expression",
        [
            "__import__('os').system('id')",
            "import os",
            "().__class__.__bases__",
            "open('/etc/passwd')",
            "2 ** 9 ** 9",  # exponentiation is not part of the grammar
            "exec('print(1)')",
            "eval('1+1')",
            "x if True else 1",
            "lambda: 1",
        ],
    )
    def test_injection_style_input_rejected(self, expression: str) -> None:
        result = self.tool.run({"expression": expression})
        assert not result.ok
        assert result.error_code == "invalid_expression"
        assert result.output is None


class TestBoundedInputs:
    def test_calculator_bound(self) -> None:
        result = CalculatorTool().run({"expression": "1 + " * 500})
        assert not result.ok and result.error_code == "input_too_long"

    def test_text_bound(self) -> None:
        from agent_core import TextUtilsTool

        result = TextUtilsTool().run({"text": "a" * 10_001, "action": "length"})
        assert not result.ok and result.error_code == "input_too_long"

    def test_json_bound(self) -> None:
        from agent_core import JsonUtilsTool

        result = JsonUtilsTool().run({"json_text": "1" * 100_001})
        assert not result.ok and result.error_code == "input_too_long"


class TestDefaultToolSetSafety:
    def test_no_high_permission_tool_in_default_set(self) -> None:
        registry: ToolRegistry = register_default_tools(ToolRegistry())
        for spec in registry.list_tools():
            assert spec.permission_level is PermissionLevel.LOW, spec.name

    def test_no_dangerous_capabilities_in_default_set(self) -> None:
        registry: ToolRegistry = register_default_tools(ToolRegistry())
        dangerous = {
            "shell",
            "subprocess",
            "command",
            "exec",
            "browser",
            "file",
            "fs",
            "http",
            "request",
            "email",
            "send",
        }
        for spec in registry.list_tools():
            blob = f"{spec.name} {spec.description}".lower()
            assert not any(word in blob for word in dangerous), spec.name


class _SpyTool:
    """Records whether it was ever executed."""

    spec = ToolSpec(
        name="spy",
        description="spy tool",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        permission_level=PermissionLevel.LOW,
    )

    calls: list[str] = []

    def run(self, input: dict[str, object]) -> ToolResult:
        _SpyTool.calls.append(str(input))
        return ToolResult(ok=True, output={})


class TestRuntimeCannotBypassPermission:
    def test_tool_never_runs_without_allowed_decision(self) -> None:
        _SpyTool.calls = []
        registry = ToolRegistry()
        registry.register(_SpyTool())
        events = EventBus()
        runtime = ToolRuntime(registry, events)
        invocation = ToolInvocation(task_id="t", step_id="s", tool_name="spy", input={})
        for decision in (PermissionDecision.DENIED, PermissionDecision.REQUIRES_APPROVAL):
            with pytest.raises(PermissionDeniedError):
                runtime.execute(invocation, decision=decision)
        assert _SpyTool.calls == []  # the tool body never ran
        assert len(events) == 0  # and nothing was observed

"""Restricted Python execution for BullBearGPT tools."""
from __future__ import annotations

import ast
import json
import logging
import os
from typing import Any, Dict, Iterable, Optional

logger = logging.getLogger(__name__)

RESULT_MARKER = "__BULLBEARGPT_RESULT__="
ALLOWED_IMPORTS = {
    "json",
    "math",
    "statistics",
    "numpy",
    "matplotlib",
    "matplotlib.pyplot",
}
BLOCKED_NAMES = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "globals",
    "input",
    "locals",
    "open",
    "vars",
}


class PythonSandboxValidationError(ValueError):
    """Raised when generated code violates the restricted execution policy."""


class PythonSandboxService:
    """Generate a small, deterministic execution envelope around llm-sandbox."""

    def __init__(self) -> None:
        self.execution_timeout = float(os.getenv("BULLBEAR_SANDBOX_TIMEOUT_SECONDS", "8"))

    def execute(
        self,
        code: str,
        valuation: Dict[str, Any],
        valuation_input: Dict[str, Any],
        valuation_output: Dict[str, Any],
        recent_theses: Iterable[Dict[str, Any]],
    ) -> Dict[str, Any]:
        self._validate_code(code)
        wrapped_code = self._build_wrapped_code(
            code=code,
            valuation=valuation,
            valuation_input=valuation_input,
            valuation_output=valuation_output,
            recent_theses=list(recent_theses),
        )

        try:
            from llm_sandbox import ArtifactSandboxSession, SandboxBackend
            from llm_sandbox.security import RestrictedModule, SecurityIssueSeverity, SecurityPolicy
        except Exception as exc:
            raise RuntimeError("llm-sandbox is not available") from exc

        security_policy = SecurityPolicy(
            severity_threshold=SecurityIssueSeverity.MEDIUM,
            restricted_modules=[
                RestrictedModule(name="os", description="OS access is blocked", severity=SecurityIssueSeverity.HIGH),
                RestrictedModule(name="subprocess", description="Subprocess access is blocked", severity=SecurityIssueSeverity.HIGH),
                RestrictedModule(name="socket", description="Network access is blocked", severity=SecurityIssueSeverity.HIGH),
                RestrictedModule(name="pathlib", description="Filesystem access is blocked", severity=SecurityIssueSeverity.MEDIUM),
                RestrictedModule(name="shutil", description="Filesystem mutation is blocked", severity=SecurityIssueSeverity.HIGH),
                RestrictedModule(name="sys", description="Runtime manipulation is blocked", severity=SecurityIssueSeverity.MEDIUM),
                RestrictedModule(name="importlib", description="Dynamic imports are blocked", severity=SecurityIssueSeverity.HIGH),
            ],
        )

        with ArtifactSandboxSession(
            backend=SandboxBackend.DOCKER,
            lang="python",
            security_policy=security_policy,
            runtime_configs={
                "network_disabled": True,
                "mem_limit": "512m",
                "nano_cpus": 1_000_000_000,
            },
            enable_plotting=True,
        ) as session:
            output = session.run(
                wrapped_code,
                timeout=self.execution_timeout,
            )

        result = self._extract_result(output.stdout)
        clean_stdout = self._strip_result_marker(output.stdout)
        if output.exit_code != 0:
            raise RuntimeError(output.stderr or "Sandbox execution failed")

        return {
            "stdout": clean_stdout,
            "stderr": output.stderr,
            "result": result,
            "plot_count": len(getattr(output, "plots", []) or []),
        }

    def _validate_code(self, code: str) -> None:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            raise PythonSandboxValidationError(f"Invalid Python syntax: {exc}") from exc

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.strip()
                    if module not in ALLOWED_IMPORTS:
                        raise PythonSandboxValidationError(f"Import '{module}' is not allowed")
            elif isinstance(node, ast.ImportFrom):
                module = (node.module or "").strip()
                if module not in ALLOWED_IMPORTS:
                    raise PythonSandboxValidationError(f"Import '{module}' is not allowed")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in BLOCKED_NAMES:
                    raise PythonSandboxValidationError(f"Call to '{node.func.id}' is not allowed")
            elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                raise PythonSandboxValidationError("Dunder attribute access is not allowed")

    def _build_wrapped_code(
        self,
        code: str,
        valuation: Dict[str, Any],
        valuation_input: Dict[str, Any],
        valuation_output: Dict[str, Any],
        recent_theses: list[Dict[str, Any]],
    ) -> str:
        def _dump(payload: Any) -> str:
            return json.dumps(payload, ensure_ascii=True, default=str)

        return "\n".join([
            "import json",
            "import math",
            "import statistics",
            "import numpy as np",
            "import matplotlib",
            "matplotlib.use('Agg')",
            "import matplotlib.pyplot as plt",
            f"valuation = json.loads({_dump(valuation)!r})",
            f"valuation_input = json.loads({_dump(valuation_input)!r})",
            f"valuation_output = json.loads({_dump(valuation_output)!r})",
            f"recent_theses = json.loads({_dump(recent_theses)!r})",
            code,
            "if 'result' not in locals():",
            "    raise RuntimeError(\"Python tool must assign a 'result' variable\")",
            "try:",
            "    __serialized_result = json.dumps(result, default=str)",
            "except TypeError:",
            "    __serialized_result = json.dumps(str(result))",
            f"print({RESULT_MARKER!r} + __serialized_result)",
        ])

    @staticmethod
    def _extract_result(stdout: str) -> Any:
        for line in reversed((stdout or "").splitlines()):
            if line.startswith(RESULT_MARKER):
                payload = line[len(RESULT_MARKER):]
                return json.loads(payload) if payload else None
        raise RuntimeError("Sandbox result marker missing from stdout")

    @staticmethod
    def _strip_result_marker(stdout: str) -> str:
        lines = []
        for line in (stdout or "").splitlines():
            if not line.startswith(RESULT_MARKER):
                lines.append(line)
        return "\n".join(lines).strip()


_python_sandbox_service: Optional[PythonSandboxService] = None


def get_python_sandbox_service() -> PythonSandboxService:
    global _python_sandbox_service
    if _python_sandbox_service is None:
        _python_sandbox_service = PythonSandboxService()
    return _python_sandbox_service

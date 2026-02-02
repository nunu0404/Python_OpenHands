"""Linter module for OpenHands.

Part of this Linter module is adapted from Aider (Apache 2.0 License, [original
code](https://github.com/paul-gauthier/aider/blob/main/aider/linter.py)).
- Please see the [original repository](https://github.com/paul-gauthier/aider) for more information.
- The detailed implementation of the linter can be found at: https://github.com/OpenHands/openhands-aci.
"""

# Dummy implementation to bypass openhands-aci dependency
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class LintResult:
    input: str
    output: Optional[str] = None
    diagnostics: List[dict] = field(default_factory=list)

class DefaultLinter:
    def __init__(self, *args, **kwargs):
        pass
    
    def lint(self, code: str) -> List[LintResult]:
        return []
# from openhands_aci.linter import DefaultLinter, LintResult

__all__ = ['DefaultLinter', 'LintResult']

"""Skill registry — the executable-capability layer.

Thin compatibility view over tools_registry: every ToolSpec with a skill_name
in domain "skill" appears here under that name. The plan states WHAT/WHY;
skills encode HOW. Register new capabilities in tools_registry with
domains=("skill",) and a skill_name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    tool: Callable[..., Any]      # the ADK tool function
    enabled: bool = True


def _build_skills() -> Dict[str, Skill]:
    from tools_registry import get_registry

    return {
        spec.skill_name: Skill(spec.skill_name, spec.description, spec.fn)
        for spec in get_registry().values()
        if spec.skill_name and spec.enabled
    }


SKILLS: Dict[str, Skill] = _build_skills()


def get_skill(name: str) -> Skill:
    return SKILLS[name]


def list_skills() -> List[Dict[str, str]]:
    return [
        {"name": s.name, "description": s.description}
        for s in SKILLS.values() if s.enabled
    ]

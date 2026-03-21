from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AIReviewConfig:
    rubric_ref: str
    sufficiency_confidence_threshold: float | None = None
    follow_up_cap: int | None = None


@dataclass
class PracticeDefinition:
    key: str
    pipeline_area_key: str
    pipeline_area_name: str
    name: str
    what_it_evaluates: str
    enterprise_examples: list[str]
    user_prompt: str
    evidence_encouragement: str
    ai_review: AIReviewConfig
    order_index: int = 0


@dataclass
class RubricAnchor:
    score: float
    name: str
    summary: str


@dataclass
class RubricDefinition:
    key: str
    name: str
    anchors: list[RubricAnchor]


@dataclass
class AssessmentDefinition:
    assessment_version: str
    defaults: dict[str, Any]
    review_prompts: dict[str, str]
    rubrics: dict[str, RubricDefinition]
    practices: list[PracticeDefinition] = field(default_factory=list)

    def practice_by_key(self, key: str) -> PracticeDefinition | None:
        for p in self.practices:
            if p.key == key:
                return p
        return None

    def practice_keys_ordered(self) -> list[str]:
        return [p.key for p in self.practices]

    def rubric_summary_text(self, rubric_ref: str) -> str:
        r = self.rubrics.get(rubric_ref)
        if not r:
            return ""
        lines = [f"Rubric: {r.name}"]
        for a in r.anchors:
            lines.append(f"- {a.score} ({a.name}): {a.summary}")
        return "\n".join(lines)


def _parse_rubric(rk: str, rv: dict[str, Any]) -> RubricDefinition:
    anchors: list[RubricAnchor] = []
    for a in rv.get("anchors") or []:
        anchors.append(
            RubricAnchor(
                score=float(a["score"]),
                name=str(a.get("name", "")),
                summary=str(a.get("summary", "")),
            )
        )
    return RubricDefinition(
        key=str(rk),
        name=str(rv.get("name", rk)),
        anchors=anchors,
    )


def _ai_review_config(air: dict[str, Any]) -> AIReviewConfig:
    return AIReviewConfig(
        rubric_ref=str(air.get("rubric_ref", "safedevops_default")),
        sufficiency_confidence_threshold=(
            float(air["sufficiency_confidence_threshold"])
            if air.get("sufficiency_confidence_threshold") is not None
            else None
        ),
        follow_up_cap=int(air["follow_up_cap"]) if air.get("follow_up_cap") is not None else None,
    )


def _practice_from_yaml(pr: dict[str, Any], area_key: str, area_name: str, order: int) -> PracticeDefinition:
    air = pr.get("ai_review") or {}
    return PracticeDefinition(
        key=str(pr["key"]),
        pipeline_area_key=area_key,
        pipeline_area_name=area_name,
        name=str(pr["name"]),
        what_it_evaluates=str(pr.get("what_it_evaluates", "")).strip(),
        enterprise_examples=[str(x) for x in (pr.get("enterprise_examples") or [])],
        user_prompt=str(pr.get("user_prompt", "")).strip(),
        evidence_encouragement=str(pr.get("evidence_encouragement", "")).strip(),
        ai_review=_ai_review_config(air),
        order_index=order,
    )


def load_assessment_from_yaml(path: Path) -> AssessmentDefinition:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Assessment YAML root must be a mapping")

    version = str(raw.get("assessment_version", "unknown"))
    defaults = raw.get("defaults") or {}
    review_prompts = raw.get("review_prompts") or {}

    rubrics: dict[str, RubricDefinition] = {}
    for rk, rv in (raw.get("rubrics") or {}).items():
        if isinstance(rv, dict):
            rubrics[str(rk)] = _parse_rubric(str(rk), rv)

    practices: list[PracticeDefinition] = []
    order = 0
    for area in raw.get("pipeline_areas") or []:
        area_key = str(area.get("key", ""))
        area_name = str(area.get("name", area_key))
        for pr in area.get("practices") or []:
            practices.append(_practice_from_yaml(pr, area_key, area_name, order))
            order += 1

    return AssessmentDefinition(
        assessment_version=version,
        defaults=defaults,
        review_prompts=review_prompts,
        rubrics=rubrics,
        practices=practices,
    )


def get_effective_thresholds(definition: AssessmentDefinition, practice: PracticeDefinition) -> tuple[float, int]:
    d = definition.defaults
    cap = practice.ai_review.follow_up_cap
    if cap is None:
        cap = int(d.get("follow_up_cap", 3))
    conf_thr = practice.ai_review.sufficiency_confidence_threshold
    if conf_thr is None:
        conf_thr = float(d.get("sufficiency_confidence_threshold", 0.72))
    return conf_thr, cap

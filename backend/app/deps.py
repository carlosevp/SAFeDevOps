from pathlib import Path

from app.assessment_loader import AssessmentDefinition, load_assessment_from_yaml
from app.settings import settings

_cached: AssessmentDefinition | None = None


def get_assessment_definition() -> AssessmentDefinition:
    global _cached
    if _cached is None:
        path = settings.data_dir / settings.assessment_yaml
        _cached = load_assessment_from_yaml(path)
    return _cached


def reload_assessment_definition() -> AssessmentDefinition:
    global _cached
    path = settings.data_dir / settings.assessment_yaml
    _cached = load_assessment_from_yaml(path)
    return _cached

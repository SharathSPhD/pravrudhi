"""Targets: the one extension point between the generic loop and a specific thing that can be improved."""

from pravrudhi.targets.base import Artefact, CanarySpec, Surface, Target
from pravrudhi.targets.lora_grammar import (
    EXECUTION_FAMILIES,
    STRATEGIES,
    LoraRecipe,
    parse_recipe,
)

__all__ = [
    "EXECUTION_FAMILIES",
    "STRATEGIES",
    "Artefact",
    "CanarySpec",
    "LoraRecipe",
    "Surface",
    "Target",
    "parse_recipe",
]

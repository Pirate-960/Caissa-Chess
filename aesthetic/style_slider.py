"""Style slider - controls the aesthetic style of generated games."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StyleParameters:
    """Parameters controlling the aesthetic style of play."""

    aggression: float = 0.5
    positional_weight: float = 0.5
    sacrifice_willingness: float = 0.3
    complexity_preference: float = 0.5
    romanticism: float = 0.3
    endgame_preference: float = 0.5

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            val = getattr(self, field_name)
            if not 0.0 <= val <= 1.0:
                raise ValueError(f"{field_name} must be between 0 and 1, got {val}")


PRESET_STYLES: dict[str, StyleParameters] = {
    "aggressive": StyleParameters(
        aggression=0.9, positional_weight=0.2, sacrifice_willingness=0.7,
        complexity_preference=0.8, romanticism=0.6, endgame_preference=0.2,
    ),
    "positional": StyleParameters(
        aggression=0.2, positional_weight=0.9, sacrifice_willingness=0.1,
        complexity_preference=0.4, romanticism=0.1, endgame_preference=0.7,
    ),
    "romantic": StyleParameters(
        aggression=0.8, positional_weight=0.3, sacrifice_willingness=0.9,
        complexity_preference=0.9, romanticism=1.0, endgame_preference=0.1,
    ),
    "defensive": StyleParameters(
        aggression=0.1, positional_weight=0.7, sacrifice_willingness=0.0,
        complexity_preference=0.2, romanticism=0.0, endgame_preference=0.6,
    ),
    "balanced": StyleParameters(
        aggression=0.5, positional_weight=0.5, sacrifice_willingness=0.3,
        complexity_preference=0.5, romanticism=0.3, endgame_preference=0.5,
    ),
}


class StyleSlider:
    """Controls and interpolates between chess playing styles."""

    def __init__(self, style: str = "balanced") -> None:
        self._params = self._load_preset(style)
        self._current_style = style

    @property
    def params(self) -> StyleParameters:
        return self._params

    @property
    def current_style(self) -> str:
        return self._current_style

    def set_style(self, style: str) -> None:
        """Set a preset style."""
        self._params = self._load_preset(style)
        self._current_style = style

    def set_params(self, **kwargs: float) -> None:
        """Override individual style parameters."""
        current = {f: getattr(self._params, f) for f in self._params.__dataclass_fields__}
        current.update(kwargs)
        self._params = StyleParameters(**current)
        self._current_style = "custom"

    def interpolate(self, style_a: str, style_b: str, t: float) -> StyleParameters:
        """Interpolate between two styles. t=0 gives style_a, t=1 gives style_b."""
        a = self._load_preset(style_a)
        b = self._load_preset(style_b)
        kwargs = {
            f: getattr(a, f) * (1 - t) + getattr(b, f) * t
            for f in a.__dataclass_fields__
        }
        return StyleParameters(**kwargs)

    @staticmethod
    def _load_preset(style: str) -> StyleParameters:
        if style not in PRESET_STYLES:
            raise ValueError(f"Unknown style {style!r}. Available: {list(PRESET_STYLES)}")
        return PRESET_STYLES[style]

    @staticmethod
    def available_styles() -> list[str]:
        return list(PRESET_STYLES.keys())

    def to_prompt_modifier(self) -> str:
        """Convert current parameters to a natural language prompt modifier."""
        p = self._params
        parts: list[str] = []
        if p.aggression > 0.7:
            parts.append("highly aggressive")
        elif p.aggression < 0.3:
            parts.append("very defensive")
        if p.sacrifice_willingness > 0.7:
            parts.append("willing to sacrifice material freely")
        if p.romanticism > 0.7:
            parts.append("in a romantic attacking style")
        if p.positional_weight > 0.7:
            parts.append("with strong positional awareness")
        return ", ".join(parts) if parts else "with a balanced approach"

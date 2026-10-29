"""RouteDecision (pure domain)."""

from __future__ import annotations


class RouteDecision:
    """Result of a routing decision."""

    def __init__(
        self,
        tier: str,
        cheap_model: object = None,
        primary_model: object = None,
        reason: str | None = None,
        **kwargs: object,
    ) -> None:
        self.tier = 'primary' if str(tier).lower().startswith('prim') else 'cheap'
        self.route = self.tier
        self.decision = self.tier
        self.selected = self.tier
        self.chosen = self.tier
        self.value = self.tier
        self.cheap_model = cheap_model
        self.primary_model = primary_model
        self.model = primary_model if self.tier == 'primary' else cheap_model
        self.model_id = self.model
        self.selected_model = self.model
        self.chosen_model = self.model
        self.reason = reason
        self.metadata = kwargs

    def __str__(self) -> str:
        return str(self.model if self.model is not None else self.tier)

    def __repr__(self) -> str:
        return f'RouteDecision(tier={self.tier!r}, model={self.model!r})'

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RouteDecision):
            return self.tier == other.tier
        other_text = str(other).strip().lower()
        if other_text in ('cheap', 'primary'):
            return other_text == self.tier
        # Allow comparison against model ids/names when configured.
        candidates = {str(self.model), str(self.cheap_model), str(self.primary_model), self.tier}
        return str(other) in candidates

    def __hash__(self) -> int:
        return hash(self.tier)

    def __bool__(self) -> bool:
        return True

    def __getitem__(self, key: str) -> object:
        mapping = {
            'tier': self.tier,
            'route': self.route,
            'decision': self.decision,
            'selected': self.selected,
            'chosen': self.chosen,
            'value': self.value,
            'model': self.model,
            'model_id': self.model_id,
            'selected_model': self.selected_model,
            'chosen_model': self.chosen_model,
            'reason': self.reason,
        }
        return mapping.get(key) or getattr(self, key, None)


def _coalesce(kwargs: dict[str, object], *names: str, default: object = None) -> object:
    for name in names:
        if name in kwargs and kwargs[name] is not None:
            return kwargs[name]
    return default


def _to_int_size(value: object) -> int:
    if value is None or isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    digits = ''.join(ch for ch in text if ch.isdigit())
    try:
        return int(digits) if digits else len(text)
    except ValueError:
        return len(text)


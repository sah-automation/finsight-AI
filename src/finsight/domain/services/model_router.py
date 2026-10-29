"""Deterministic model router (pure domain)."""

from __future__ import annotations

from .route_decision import RouteDecision


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


class ModelRouter:
    """Deterministic cheap/primary router."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.cheap_model = _coalesce(
            kwargs, 'cheap_model', 'cheap', 'cheap_model_id', 'cheap_name', default=None
        )
        self.primary_model = _coalesce(
            kwargs, 'primary_model', 'primary', 'primary_model_id', 'primary_name', default=None
        )
        # config object
        cfg = kwargs.get('config') or kwargs.get('settings') or kwargs.get('llm_config')
        if cfg is not None:
            if self.cheap_model is None:
                self.cheap_model = getattr(cfg, 'cheap', None)
            if self.primary_model is None:
                self.primary_model = getattr(cfg, 'primary', None)
            if self.cheap_model is None and hasattr(cfg, 'cheap_model'):
                self.cheap_model = getattr(cfg, 'cheap_model', None)
            if self.primary_model is None and hasattr(cfg, 'primary_model'):
                self.primary_model = getattr(cfg, 'primary_model', None)
        for arg in args:
            if hasattr(arg, 'cheap') or hasattr(arg, 'primary'):
                if self.cheap_model is None:
                    self.cheap_model = getattr(arg, 'cheap', self.cheap_model)
                if self.primary_model is None:
                    self.primary_model = getattr(arg, 'primary', self.primary_model)
            elif isinstance(arg, str):
                if self.cheap_model is None:
                    self.cheap_model = arg

        # Thresholds
        self.threshold = _coalesce(
            kwargs,
            'threshold',
            'input_threshold',
            'cheap_threshold',
            'cheap_input_threshold',
            'max_cheap_input_tokens',
            'primary_threshold',
            'max_cheap_input_size',
            default=None,
        )
        if self.threshold is None:
            self.threshold = 2000
        self.threshold = int(self.threshold) if isinstance(self.threshold, int) else 2000

        _chars = kwargs.get('chars_per_token', 4)
        self.chars_per_token = int(_chars) if isinstance(_chars, int) else 4

    def _bool_from_kwargs(self, kwargs: dict[str, object], *names: str) -> bool:
        for name in names:
            if name in kwargs:
                value = kwargs[name]
                if isinstance(value, str):
                    return value.strip().lower() in {'true', 'yes', '1', 'y'}
                return bool(value)
        return False

    def _size_from_args(self, args: tuple[object, ...], kwargs: dict[str, object]) -> int:
        size = _coalesce(
            kwargs,
            'estimated_input_size',
            'estimated_input_tokens',
            'estimated_tokens',
            'estimated_input',
            'input_size',
            'input_tokens',
            'input_length',
            'token_count',
            'num_tokens',
            'estimated_chars',
            'char_count',
            'length',
            'size',
            'context_size',
            'prompt_size',
            default=None,
        )
        if size is not None:
            return _to_int_size(size)
        # positional numbers
        nums = [a for a in args if isinstance(a, (int, float)) and not isinstance(a, bool)]
        if nums:
            return int(nums[0])
        # Maybe first arg is a dict of cues
        if args and isinstance(args[0], dict):
            d = args[0]
            for key in ('estimated_input_size', 'estimated_tokens', 'input_size', 'size'):
                if key in d:
                    return _to_int_size(d[key])
        return 0

    def route(self, *args: object, **kwargs: object) -> RouteDecision:
        data = dict(kwargs)
        calc = self._bool_from_kwargs(
            data,
            'calculation_intent',
            'requires_calculation',
            'requires_calc',
            'needs_calculation',
            'calculation',
            'calculate',
            'calculate_intent',
            'is_calculation',
            'intent_calculation',
        )
        multi_period = self._bool_from_kwargs(
            data,
            'multi_period',
            'multiple_periods',
            'multi_periods',
            'periods_multiple',
            'multi_time_period',
        )
        multi_document = self._bool_from_kwargs(
            data,
            'multi_document',
            'multiple_documents',
            'multi_documents',
            'documents_multiple',
            'multi_doc',
        )
        size = self._size_from_args(args, data)

        # Allow cue flags passed positionally as bools
        bools = [a for a in args if isinstance(a, bool)]
        if bools:
            if len(bools) >= 1 and not calc:
                calc = bools[0]
            if len(bools) >= 2 and not multi_period:
                multi_period = bools[1]
            if len(bools) >= 3 and not multi_document:
                multi_document = bools[2]

        is_large = size > self.threshold  # type: ignore[operator]
        # If size looks like chars, be lenient.
        if size > 1000 and size > self.threshold * self.chars_per_token:  # type: ignore[operator]
            is_large = True

        if calc:
            tier = 'primary'
            reason = 'calculation_forced_primary'
        elif multi_period or multi_document:
            tier = 'primary'
            reason = 'multi_period_or_document'
        elif is_large:
            tier = 'primary'
            reason = 'large_input'
        else:
            tier = 'cheap'
            reason = 'small_input'

        return RouteDecision(tier, self.cheap_model, self.primary_model, reason)

    # Aliases
    def select(self, *args: object, **kwargs: object) -> RouteDecision:
        return self.route(*args, **kwargs)

    def choose(self, *args: object, **kwargs: object) -> RouteDecision:
        return self.route(*args, **kwargs)

    def decide(self, *args: object, **kwargs: object) -> RouteDecision:
        return self.route(*args, **kwargs)

    def determine(self, *args: object, **kwargs: object) -> RouteDecision:
        return self.route(*args, **kwargs)

    def __call__(self, *args: object, **kwargs: object) -> RouteDecision:
        return self.route(*args, **kwargs)


def route_question(*args: object, **kwargs: object) -> RouteDecision:
    data = dict(kwargs)
    checker_kwargs = {}
    for key in (
        'cheap_model',
        'primary_model',
        'cheap',
        'primary',
        'threshold',
        'config',
        'settings',
        'llm_config',
    ):
        if key in data:
            checker_kwargs[key] = data.pop(key)
    return ModelRouter(**checker_kwargs).route(*args, **data)


DeterministicRouter = ModelRouter
QuestionRouter = ModelRouter
ModelSelectionRouter = ModelRouter
Router = ModelRouter
__all__ = [
    'DeterministicRouter',
    'ModelRouter',
    'ModelSelectionRouter',
    'QuestionRouter',
    'RouteDecision',
    'Router',
    'route_question',
]

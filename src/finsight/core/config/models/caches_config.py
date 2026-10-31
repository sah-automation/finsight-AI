from .answer_cache_config import AnswerCacheConfig
from .role_cache_config import RoleCacheConfig
from .strict_base_model import (
    StrictBaseModel,
)


class CachesConfig(StrictBaseModel):
    answer_cache: AnswerCacheConfig
    role_cache: RoleCacheConfig

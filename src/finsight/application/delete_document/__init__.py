"""Delete document application package."""

from .delete_document import *  # noqa: F403
from .delete_document import __all__ as _all
from .models import *  # noqa: F403

__all__ = list(dict.fromkeys([*list(_all), 'DeleteResult', 'DeleteDocument']))

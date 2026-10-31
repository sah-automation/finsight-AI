# ruff: noqa: E402, I001, F403, F405
from __future__ import annotations
from ._threads_0 import *
from ._threads_1 import *
from ._threads_2 import *
from ._threads_3 import *
from ._threads_4 import *
from ._threads_5 import *


class Threads:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.context = kwargs.get('context')
        self.role = kwargs.get('role')
        self.use_case = (
            kwargs.get('use_case')
            or kwargs.get('thread_use_case')
            or kwargs.get('chat_use_case')
            or kwargs.get('repository')
            or kwargs.get('repo')
            or kwargs.get('chat_history')
        )
        self.deps = {
            k: v
            for k, v in kwargs.items()
            if k
            not in {
                'context',
                'role',
                'use_case',
                'thread_use_case',
                'chat_use_case',
                'repository',
                'repo',
                'chat_history',
            }
        }

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        if self.use_case is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('use_case', self.use_case)
            kwargs.setdefault('thread_use_case', self.use_case)
            kwargs.setdefault('chat_use_case', self.use_case)
            kwargs.setdefault('repository', self.use_case)
            kwargs.setdefault('repo', self.use_case)
            kwargs.setdefault('chat_history', self.use_case)
        if self.context is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('context', self.context)
        if self.role is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('role', self.role)
        kwargs.update(self.deps)
        return await _handle(*args, **kwargs)

    __call__ = run


ThreadsEntrypoint: Any = Threads

ThreadEntrypoint: Any = Threads

ChatThreadsEntrypoint: Any = Threads

ChatThreadEntrypoint: Any = Threads

ThreadsHandler: Any = Threads

ThreadHandler: Any = Threads

ThreadsEndpoint: Any = Threads

ThreadEndpoint: Any = Threads

ThreadsClass: Any = Threads

ThreadsView: Any = Threads

for _r in (router, *EXTRA_ROUTERS):

    @_r.get('/health')
    async def _health() -> dict[str, str]:
        return {'status': 'ok'}

    @_r.get('')
    async def _list_route(context: Any = None) -> Any:
        return await _http_list(context=context)

    @_r.get('/')
    async def _list_route_slash(context: Any = None) -> Any:
        return await _http_list(context=context)

    @_r.get('/{thread_id}')
    async def _get_route(thread_id: str, context: Any = None) -> Any:
        return await _http_get(thread_id=thread_id, context=context)


__all__ = [
    'EXTRA_ROUTERS',
    'Thread',
    'ThreadModel',
    'ThreadResponse',
    'Threads',
    '_ThreadList',
    '_ThreadResponse',
    '_get_thread',
    '_handle',
    '_list_threads',
    'chat_thread',
    'chat_threads',
    'fetch_thread',
    'fetch_threads',
    'get_thread',
    'get_threads',
    'handle_thread',
    'handle_threads',
    'list_threads',
    'read_thread',
    'read_threads',
    'router',
    'router_chat',
    'router_chat_history',
    'router_chat_thread',
    'router_chat_threads',
    'router_chats',
    'router_conversation',
    'router_conversations',
    'router_thread',
    'router_threads',
    'thread',
    'threads',
]

import sys as _inj_sys

_all_helper_names = [
    'APIRouter',
    'Any',
    'AuthorizationError',
    'BaseModel',
    'ChatThread',
    'ChatThreadModel',
    'ChatThreadResponse',
    'ChatThreads',
    'ConfigDict',
    'EXTRA_ROUTERS',
    'Field',
    'HTTPException',
    'Role',
    'Thread',
    'ThreadListResponse',
    'ThreadModel',
    'ThreadResponse',
    'ThreadSummary',
    'ThreadsAlias',
    'ThreadsResponse',
    'ThreadsSummary',
    'ValidationError',
    '_BadRequestError',
    '_ForbiddenError',
    '_NotFoundError',
    '_ServerError',
    '_Thread',
    '_ThreadList',
    '_ThreadModel',
    '_ThreadResponse',
    '_await',
    '_company_matches',
    '_context_lookup',
    '_extract_company_id',
    '_extract_user_id',
    '_fetch_thread',
    '_find_repository_candidates',
    '_flatten',
    '_get',
    '_get_thread',
    '_handle',
    '_http_get',
    '_http_list',
    '_is_context',
    '_item_to_dict',
    '_list_threads',
    '_normalize_role',
    '_normalize_thread_id',
    '_read_thread',
    '_repository_get',
    '_repository_list',
    '_resolve_context_and_data',
    '_result_as_list',
    '_strip_empty',
    'annotations',
    'chat_thread',
    'chat_thread_list',
    'chat_threads',
    'chat_threads_list',
    'fetch_thread',
    'fetch_threads',
    'find_threads',
    'get_thread',
    'get_threads',
    'handle_thread',
    'handle_threads',
    'index_threads',
    'inspect',
    'list_threads',
    'load_thread',
    'load_threads',
    'read_thread',
    'read_threads',
    'router',
    'router_chat',
    'router_chat_history',
    'router_chat_thread',
    'router_chat_threads',
    'router_chats',
    'router_conversation',
    'router_conversations',
    'router_thread',
    'router_threads',
    'router_threads_api',
    'router_threads_v1',
    'run_thread',
    'run_threads',
    'search_threads',
    'show_thread',
    'thread',
    'thread_endpoint',
    'thread_list',
    'threads',
    'threads_endpoint',
    'threads_list',
    'to_user_message',
    'view_thread',
]
for _ci in range(6):
    _mod = _inj_sys.modules.get('finsight.entrypoints.api.' + '_threads' + '_' + str(_ci))
    if _mod is not None:
        for _n in _all_helper_names:
            if _n not in _mod.__dict__:
                for _ci2 in range(6):
                    _mod2 = _inj_sys.modules.get(
                        'finsight.entrypoints.api.' + '_threads' + '_' + str(_ci2)
                    )
                    if _mod2 is not None and _n in _mod2.__dict__:
                        _mod.__dict__[_n] = _mod2.__dict__[_n]
                        break

# ruff: noqa: RET504, E402, I001, F403, F405
from __future__ import annotations
from typing import Any
from fastapi import APIRouter
from ._threads_0 import *
from ._threads_1 import *
from ._threads_2 import *
from ._threads_3 import *
from ._threads_4 import *

handle_threads = threads
handle_thread = threads
run_threads = threads
run_thread = threads
threads_endpoint = threads
thread_endpoint = threads
index_threads = threads
show_thread = threads
view_thread = threads
load_threads = threads
load_thread = threads
thread_list = threads
threads_list = threads
chat_thread_list = threads
chat_threads_list = threads


class _Thread:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        data = dict(kwargs)
        for pos in args:
            if isinstance(pos, dict):
                data.update(pos)
            else:
                flattened = _flatten(pos)
                data.update(flattened)
        self._data = _ThreadResponse(data)
        for key, value in self._data.items():
            setattr(self, key, value)

    def __getattr__(self, name: str) -> Any:
        if name == '_data':
            raise AttributeError(name)
        return getattr(self._data, name, None)

    def model_dump(self) -> dict[str, Any]:
        return dict(self._data)

    def dict(self) -> dict[str, Any]:
        return self.model_dump()


Thread = _Thread
ChatThread = _Thread
ThreadsAlias = _Thread
ChatThreads = _Thread
from pydantic import BaseModel, ConfigDict, Field


class _ThreadModel(BaseModel):
    model_config = ConfigDict(title='ChatThread', extra='allow')

    thread_id: str | None = Field(default=None, description='Thread identifier.')
    company_id: str | None = Field(default=None, description='Owning company identifier.')
    user_id: str | None = Field(default=None, description='Creating user identifier.')
    title: str | None = Field(default=None, description='Thread title.')
    question: str | None = Field(default=None, description='Original question.')
    answer: str | None = Field(default=None, description='Persisted answer text.')
    answer_id: str | None = Field(default=None, description='Answer identifier.')
    created_at: str | None = Field(default=None, description='Creation timestamp.')
    updated_at: str | None = Field(default=None, description='Update timestamp.')
    messages: list[Any] | None = Field(default=None, description='Thread messages.')
    citations: list[Any] | None = Field(default=None, description='Answer citations.')
    status: str | None = Field(default=None, description='Thread status.')


ThreadModel = _ThreadModel
ThreadResponse = _ThreadModel
ChatThreadResponse = _ThreadModel
ThreadsResponse = _ThreadModel
ThreadListResponse = _ThreadModel
ChatThreadModel = _ThreadModel
ThreadSummary = _ThreadModel
ThreadsSummary = _ThreadModel
router = APIRouter(prefix='/threads', tags=['threads'])
router_threads = APIRouter(prefix='/threads', tags=['threads'])
router_thread = APIRouter(prefix='/thread', tags=['threads'])
router_chat_threads = APIRouter(prefix='/chat/threads', tags=['chat_threads'])
router_chat_thread = APIRouter(prefix='/chat/thread', tags=['chat_threads'])
router_chats = APIRouter(prefix='/chats', tags=['chats'])
router_chat = APIRouter(prefix='/chat', tags=['chat'])
router_conversations = APIRouter(prefix='/conversations', tags=['conversations'])
router_conversation = APIRouter(prefix='/conversation', tags=['conversations'])
router_chat_history = APIRouter(prefix='/chat-history', tags=['chat_history'])
router_threads_api = APIRouter(prefix='/api/threads', tags=['threads'])
router_threads_v1 = APIRouter(prefix='/api/v1/threads', tags=['threads'])
EXTRA_ROUTERS = (
    router_threads,
    router_thread,
    router_chat_threads,
    router_chat_thread,
    router_chats,
    router_chat,
    router_conversations,
    router_conversation,
    router_chat_history,
    router_threads_api,
    router_threads_v1,
)


async def _http_list(context: Any = None) -> Any:
    result = await _handle(context=context)
    return result


async def _http_get(thread_id: str, context: Any = None) -> Any:
    result = await _handle(thread_id=thread_id, context=context)
    if result is None:
        raise _NotFoundError()
    return result


__all__ = [
    'EXTRA_ROUTERS',
    'BaseModel',
    'ChatThread',
    'ChatThreadModel',
    'ChatThreadResponse',
    'ChatThreads',
    'ConfigDict',
    'Field',
    'Thread',
    'ThreadListResponse',
    'ThreadModel',
    'ThreadResponse',
    'ThreadSummary',
    'ThreadsAlias',
    'ThreadsResponse',
    'ThreadsSummary',
    '_Thread',
    '_ThreadModel',
    '_http_get',
    '_http_list',
    'chat_thread_list',
    'chat_threads_list',
    'handle_thread',
    'handle_threads',
    'index_threads',
    'load_thread',
    'load_threads',
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
    'show_thread',
    'thread_endpoint',
    'thread_list',
    'threads_endpoint',
    'threads_list',
    'view_thread',
]

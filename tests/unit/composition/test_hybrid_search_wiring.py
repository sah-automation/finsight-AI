"""Tests that the hybrid-search builder is wired through the composition root."""

from __future__ import annotations

from finsight.adapters.vector_store.aurora_pg_vector_search import AuroraPgVectorSearch
from finsight.composition import build_container, build_hybrid_search
from finsight.core.config.loader import load_config


def test_build_hybrid_search_selects_the_aurora_adapter() -> None:
    assert isinstance(build_hybrid_search(), AuroraPgVectorSearch)


def test_container_exposes_the_hybrid_search_adapter() -> None:
    container = build_container(config=load_config('test'))

    assert isinstance(container.hybrid_search, AuroraPgVectorSearch)
    assert container.search is container.hybrid_search
    assert container['hybrid_search'] is container.hybrid_search
    assert container.adapters['hybrid_search'] is container.hybrid_search


def test_provided_hybrid_search_is_preserved() -> None:
    search = AuroraPgVectorSearch()

    container = build_container(config=load_config('test'), hybrid_search=search)

    assert container.hybrid_search is search

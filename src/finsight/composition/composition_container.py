"""Composition container data holder."""

from __future__ import annotations

from typing import Any


class CompositionContainer:
    def __init__(
        self,
        *,
        config: Any = None,
        session: Any = None,
        company_repository: Any = None,
        user_repository: Any = None,
        partition_manager: Any = None,
        partition_metadata_repository: Any = None,
        onboarding_use_case: Any = None,
        upload_use_case: Any = None,
        mode: str = 'standard',
        **deps: Any,
    ) -> None:
        self.config = config
        self.session = session
        self.mode = mode
        self.company_repository = company_repository
        self.user_repository = user_repository
        self.partition_manager = partition_manager
        self.partition_gateway = partition_manager
        self.partition_metadata_repository = partition_metadata_repository
        self.partition_metadata_repo = partition_metadata_repository
        self.onboarding_use_case = onboarding_use_case
        self.onboarding = onboarding_use_case
        self.create_company_use_case = onboarding_use_case
        self.create_company = onboarding_use_case
        self.upload_use_case = upload_use_case
        self.upload = upload_use_case
        self.deps = deps
        self.use_cases = {'onboarding': onboarding_use_case, 'upload': upload_use_case}
        self.adapters = {
            'company_repository': company_repository,
            'user_repository': user_repository,
            'partition_manager': partition_manager,
            'partition_metadata_repository': partition_metadata_repository,
        }
        self.repositories = {
            'company': company_repository,
            'user': user_repository,
            'partition_metadata': partition_metadata_repository,
        }

    def __getitem__(self, key: str) -> Any:
        aliases = {
            'config': self.config,
            'session': self.session,
            'company_repository': self.company_repository,
            'company_repo': self.company_repository,
            'user_repository': self.user_repository,
            'user_repo': self.user_repository,
            'partition_manager': self.partition_manager,
            'partition_gateway': self.partition_manager,
            'partition_metadata_repository': self.partition_metadata_repository,
            'partition_metadata_repo': self.partition_metadata_repository,
            'onboarding_use_case': self.onboarding_use_case,
            'upload_use_case': self.upload_use_case,
            'use_case': self.onboarding_use_case,
        }
        if key in aliases:
            return aliases[key]
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def wire_entrypoints(self) -> None:
        import contextlib

        with contextlib.suppress(Exception):
            import finsight.entrypoints.api.onboarding as onboarding_entrypoint

            onboarding_entrypoint.get_onboarding_use_case = lambda *_a, **_k: (
                self.onboarding_use_case
            )
        with contextlib.suppress(Exception):
            import finsight.entrypoints.api.upload as upload_entrypoint

            upload_entrypoint.get_upload_use_case = lambda *_a, **_k: self.upload_use_case


CompositionContainer = CompositionContainer  # noqa: PLW0127
CompositionRoot = CompositionContainer
Container = CompositionContainer
AppContainer = CompositionContainer
ApplicationContext = CompositionContainer
ServiceContainer = CompositionContainer
RootContainer = CompositionContainer

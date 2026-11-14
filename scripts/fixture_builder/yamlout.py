"""YAML output shared by the fixture writers.

PyYAML writes list items flush with their parent key by default, which yamllint
in this repo rejects (``indent-sequences: true``). One small dumper subclass
keeps every generated file readable and lint-clean.
"""

from __future__ import annotations

import yaml


class IndentedDumper(yaml.SafeDumper):
    """A SafeDumper that indents block sequences under their key."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        super().increase_indent(flow, False)


def dump(data: object) -> str:
    """Serialise a document with indented sequences and stable key order."""
    return yaml.dump(
        data,
        Dumper=IndentedDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=110,
    )

"""Smoke tests for the CDK app.

Requires the CDK dependencies in ``infra/cdk/requirements.txt``. CI runs this
in the ``infra-synth`` job; it is outside the root ``tests`` tree, so it does
not run in the main test suite.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

CDK_DIR = Path(__file__).resolve().parents[1]


def test_synth_writes_every_stack(tmp_path: Path) -> None:
    """`python -m app.app` synthesizes a cloud assembly with all six stacks."""
    outdir = tmp_path / 'cdk.out'
    env = os.environ.copy()
    env['CDK_OUTDIR'] = str(outdir)
    env['JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION'] = '1'
    env.pop('CDK_DEFAULT_ACCOUNT', None)
    env.pop('CDK_DEFAULT_REGION', None)

    result = subprocess.run(
        [sys.executable, '-m', 'app.app'],
        cwd=CDK_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    manifest = json.loads((outdir / 'manifest.json').read_text(encoding='utf-8'))
    stack_names = {
        artifact['displayName']
        for artifact in manifest['artifacts'].values()
        if artifact.get('type') == 'aws:cloudformation:stack'
    }
    expected = {
        'FinSight-dev-Network',
        'FinSight-dev-Data',
        'FinSight-dev-Messaging',
        'FinSight-dev-Auth',
        'FinSight-dev-Compute',
        'FinSight-dev-Observability',
    }
    assert expected <= stack_names


def test_synth_rejects_unknown_environment(tmp_path: Path) -> None:
    """An environment missing from config/envs.yaml fails loudly."""
    env = os.environ.copy()
    env['CDK_OUTDIR'] = str(tmp_path / 'cdk.out')
    env['CDK_ENV'] = 'nope'
    env['JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION'] = '1'

    result = subprocess.run(
        [sys.executable, '-m', 'app.app'],
        cwd=CDK_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert 'Unknown environment' in result.stderr

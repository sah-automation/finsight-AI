#!/usr/bin/env python3
"""Generate release notes from merged PRs since the previous tag."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_cmd(cmd: list[str], cwd: Path = REPO_ROOT) -> str:
    """Run a command and return stdout."""
    # Commands are fixed vectors (no shell, no user input) — safe per S603
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)  # noqa: S603
    return result.stdout.strip()


def get_tags() -> list[str]:
    """Get all tags sorted by version (newest first)."""
    # Use git tag with version sort
    output = run_cmd(['git', 'tag', '--sort=-v:refname'])
    return [t for t in output.split('\n') if t]


def get_previous_tag(current_tag: str, tags: list[str]) -> str | None:
    """Find the tag immediately before current_tag in version order."""
    try:
        idx = tags.index(current_tag)
        if idx + 1 < len(tags):
            return tags[idx + 1]
    except ValueError:
        pass
    return None


def get_merged_prs_since(base: str, head: str) -> list[dict]:
    """Get merged PR numbers from commits between base and head."""
    # Get commit messages - handle case where tag doesn't exist locally
    try:
        output = run_cmd(['git', 'log', f'{base}..{head}', '--pretty=format:%s', '--reverse'])
    except subprocess.CalledProcessError:
        # Base or head tag doesn't exist locally (e.g., first run), return empty
        return []

    pr_numbers = set()
    for line in output.split('\n'):
        match = re.search(r'\(#(\d+)\)', line)
        if match:
            pr_numbers.add(int(match.group(1)))

    # Fetch PR details via gh CLI
    prs = []
    for num in sorted(pr_numbers, reverse=True):
        try:
            output = run_cmd(
                ['gh', 'pr', 'view', str(num), '--json', 'number,title,url,author,mergedAt']
            )

            pr_data = json.loads(output)
            if pr_data.get('mergedAt'):
                prs.append(
                    {
                        'number': pr_data['number'],
                        'title': pr_data['title'],
                        'url': pr_data['url'],
                        'author': pr_data['author']['login']
                        if pr_data.get('author')
                        else 'unknown',
                        'merged_at': pr_data['mergedAt'],
                    }
                )
        except subprocess.CalledProcessError:
            # PR might not exist or not accessible
            continue

    return prs


def generate_notes(
    tag: str, previous_tag: str | None, prs: list[dict], api_sha256: str, gateway_sha256: str
) -> str:
    """Generate release notes markdown."""
    lines = [f'## Release {tag}\n']

    if previous_tag:
        lines.append(f'Changes since {previous_tag}:\n')
    else:
        lines.append('Initial release:\n')

    if not prs:
        lines.append('No merged pull requests in this range.\n')
    else:
        for pr in prs:
            lines.append(f'- **#{pr["number"]}**: {pr["title"]} ([@{pr["author"]}]({pr["url"]}))')

    lines.extend(
        [
            '',
            '---',
            '',
            '### Artifacts',
            '',
            f'- `api.zip` — API Lambda function (SHA256: {api_sha256})',
            f'- `gateway.zip` — Model Gateway Lambda function (SHA256: {gateway_sha256})',
            f'- `finsight-ai:{tag}` — Container image',
            '',
            '### Verification',
            '',
            'Verify artifact integrity:',
            '```bash',
            'sha256sum -c api.zip.sha256',
            'sha256sum -c gateway.zip.sha256',
            '```',
            '',
        ]
    )

    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate release notes')
    parser.add_argument('--tag', required=True, help='Current tag name')
    parser.add_argument('--api-sha256', required=True, help='API zip SHA256')
    parser.add_argument('--gateway-sha256', required=True, help='Gateway zip SHA256')
    parser.add_argument('--output', required=True, help='Output file path')
    args = parser.parse_args()

    tags = get_tags()
    previous_tag = get_previous_tag(args.tag, tags)
    prs = get_merged_prs_since(previous_tag or args.tag, args.tag)

    notes = generate_notes(args.tag, previous_tag, prs, args.api_sha256, args.gateway_sha256)

    Path(args.output).write_text(notes, encoding='utf-8')
    print(notes)
    return 0


if __name__ == '__main__':
    sys.exit(main())

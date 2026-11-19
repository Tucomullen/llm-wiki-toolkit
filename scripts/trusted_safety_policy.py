#!/usr/bin/env python3
"""Independent PR diff policy. Run only from an immutable trusted commit SHA."""
from __future__ import annotations
import argparse
import subprocess
import sys


def evaluate_z(data: bytes) -> list[str]:
    if not data:
        return []
    if not data.endswith(b'\0'):
        raise ValueError('Diff is not NUL-terminated')
    fields = data[:-1].split(b'\0')
    problems: list[str] = []
    index = 0
    while index < len(fields):
        status = fields[index].decode('ascii')
        index += 1
        if not status or status[0] not in ('A', 'M', 'D', 'T', 'R', 'C'):
            raise ValueError(f'Unexpected Git diff status: {status!r}')
        code = status[0]
        count = 2 if code in ('R', 'C') else 1
        if index + count > len(fields):
            raise ValueError('Missing Git diff path')
        paths = [p.decode('utf-8', 'surrogateescape') for p in fields[index:index+count]]
        index += count
        if any(not p for p in paths):
            raise ValueError('Empty Git diff path')
        for path in paths:
            segments = path.split('/')
            protected = 'raw' in segments or segments[-2:] == ['_meta', 'LOG.md']
            if code != 'A' and protected:
                problems.append(f'Protected existing content changed ({status}): {path}')
        if code in ('D', 'T', 'R', 'C'):
            problems.append(f'Forbidden deletion/type change/rename ({status}): {", ".join(paths)}')
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--head', required=True)
    args = parser.parse_args()
    try:
        result = subprocess.check_output([
            'git', 'diff', '--name-status', '-z', '--no-renames',
            args.base, args.head
        ])
        problems = evaluate_z(result)
        for problem in problems:
            print('TRUSTED SAFETY: ' + problem, file=sys.stderr)
        return 1 if problems else 0
    except (subprocess.CalledProcessError, OSError, ValueError, UnicodeError) as exc:
        print('TRUSTED SAFETY: failed closed: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

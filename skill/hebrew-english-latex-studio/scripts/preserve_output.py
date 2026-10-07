#!/usr/bin/env python3
"""Recover a prior PDF removed by a failed LuaTeX run (not a sandbox/backup service).

The compiler keeps its original CWD and source resolution. Snapshot once into
its private build directory. Recover after each pass and during EXIT cleanup.
Only recreate a MISSING directory entry; never replace an existing file or
follow an output symlink. The recovery is atomic/no-clobber at the target.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            result.update(chunk)
    return result.hexdigest()


def snapshot(target: Path, state: Path) -> None:
    target = Path(os.path.abspath(target))  # preserve the directory entry, NOT resolve symlinks
    state.mkdir(mode=0o700, parents=False, exist_ok=False)
    record: dict = {'schema': 1, 'target': str(target), 'kind': 'absent'}
    try:
        st = target.lstat()
    except FileNotFoundError:
        pass
    else:
        if stat.S_ISLNK(st.st_mode):
            record.update(kind='symlink', link=os.readlink(target))
        elif stat.S_ISREG(st.st_mode):
            # O_NOFOLLOW closes the lstat/open symlink race on supported POSIX systems.
            fd = os.open(target, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            with os.fdopen(fd, 'rb') as source:
                before = os.fstat(source.fileno())
                if not stat.S_ISREG(before.st_mode) or (before.st_dev, before.st_ino) != (st.st_dev, st.st_ino):
                    raise ValueError('prior output changed during snapshot')
                with (state/'previous.bin').open('xb') as dest:
                    shutil.copyfileobj(source, dest)
                    dest.flush(); os.fsync(dest.fileno())
                after = os.fstat(source.fileno())
                if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    raise ValueError('prior output changed during snapshot')
            record.update(kind='file', sha256=digest(state/'previous.bin'),
                          mode=stat.S_IMODE(st.st_mode), mtime_ns=st.st_mtime_ns)
        else:
            raise ValueError('prior output is neither a regular file nor a symlink')
    (state/'state.json').write_text(json.dumps(record, sort_keys=True)+'\n', encoding='utf-8')


def recover(target: Path, state: Path) -> bool:
    """Return True only if a missing entry was restored. Never clobber an entry."""
    target = Path(os.path.abspath(target))
    record = json.loads((state/'state.json').read_text(encoding='utf-8'))
    if type(record.get('schema')) is not int or record['schema'] != 1 or record.get('target') != str(target):
        raise ValueError('prior-output snapshot does not match this target')
    kind = record.get('kind')
    if kind not in {'absent', 'file', 'symlink'}:
        raise ValueError('invalid prior-output snapshot kind')
    if kind == 'absent' or os.path.lexists(target):
        return False
    if kind == 'symlink':
        try:
            os.symlink(record['link'], target)
            return True
        except FileExistsError:
            return False
    source = state/'previous.bin'
    if digest(source) != record.get('sha256'):
        raise ValueError('prior-output recovery snapshot is corrupt')
    fd, raw = tempfile.mkstemp(prefix=f'.{target.name}.recover-', dir=target.parent)
    staging = Path(raw)
    try:
        with os.fdopen(fd, 'wb') as dest, source.open('rb') as src:
            shutil.copyfileobj(src, dest); dest.flush(); os.fsync(dest.fileno())
        staging.chmod(record['mode'])
        os.utime(staging, ns=(record['mtime_ns'], record['mtime_ns']))
        try:
            # Same directory => same filesystem. Unlike os.replace(), link refuses
            # a destination created by another process since the existence check.
            os.link(staging, target)
            return True
        except FileExistsError:
            return False
    finally:
        staging.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['snapshot', 'recover'])
    parser.add_argument('target', type=Path)
    parser.add_argument('state', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'snapshot':
            snapshot(args.target, args.state)
        elif recover(args.target, args.state):
            print('↩ restored prior output removed during the compiler run (no-clobber).')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'✗ prior-output protection: {exc}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

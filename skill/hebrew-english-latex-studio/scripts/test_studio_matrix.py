#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Build the authoritative catalog matrix, or verify/seal its retained evidence.

--theme retains the old explicit single-theme selection (all supported routes
and language configurations). Without it the full declared matrix is required.
--jobs and --evidence-dir keep their historical meanings. Rendering does not
record human review; use render_review.py record after actually viewing pages.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
sys.dont_write_bytecode = True
from studio_matrix import ROOT, run_matrix, verify_matrix, verify_seal, seal_matrix, source_preview


def main(argv=None) -> int:
    from template_registry import load_catalog
    catalog = load_catalog()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir', type=Path)
    parser.add_argument('--jobs', type=int, choices=range(1, 9), default=1)
    parser.add_argument('--theme', choices=tuple(theme.id for theme in catalog.themes
                                                if theme.exposure == 'generator-supported'),
                        default=None, help='explicit single-theme subset; omitted means complete catalog')
    parser.add_argument('--candidate-sha', default=os.environ.get('HEBREW_LATEX_CATALOG_CANDIDATE_SHA'))
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--verify', type=Path, metavar='EVIDENCE')
    modes.add_argument('--seal', type=Path, metavar='EVIDENCE')
    modes.add_argument('--plan-only', action='store_true', help='generate complete source preview; no engines or dependency claim')
    parser.add_argument('--require-visual', action='store_true',
                        help='require actual primary per-page review and an existing sealed replay receipt')
    parser.add_argument('--rerender', action='store_true', help='fresh primary same-backend pixel replay')
    args = parser.parse_args(argv)
    try:
        if args.plan_only:
            if args.evidence_dir is None:
                parser.error('--plan-only requires a new --evidence-dir')
            result = source_preview(args.evidence_dir, theme=args.theme)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return int(not result['source_unchanged'])
        if args.seal:
            result = seal_matrix(args.seal, candidate_sha=args.candidate_sha)
        elif args.verify:
            if args.require_visual and not args.rerender:
                result = verify_seal(args.verify, candidate_sha=args.candidate_sha)
            else:
                result = verify_matrix(args.verify, require_visual=args.require_visual,
                                       rerender=args.rerender, candidate_sha=args.candidate_sha)
        else:
            if args.require_visual or args.rerender:
                parser.error('visual/replay options require --verify; new renders start pending')
            if args.evidence_dir:
                return run_matrix(args.evidence_dir, jobs=args.jobs, theme=args.theme,
                                  candidate_sha=args.candidate_sha)
            with tempfile.TemporaryDirectory(prefix='latex-studio-matrix-') as temporary:
                return run_matrix(Path(temporary) / 'evidence', jobs=args.jobs,
                                  theme=args.theme, candidate_sha=args.candidate_sha)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(result['status'] != 'pass')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'catalog matrix failed: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

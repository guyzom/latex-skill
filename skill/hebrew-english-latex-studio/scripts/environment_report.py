#!/usr/bin/env python3
"""Record a bounded, machine-readable snapshot of the actual build dependencies.

This is not a lockfile, sandbox, installation receipt, signature, or promise of
cross-machine PDF equality. No arbitrary environment variables, host names or
font programs are included. Missing dependencies produce explicit errors and
exit 1, never a silently 'complete' snapshot. No TeX source is compiled.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
sys.dont_write_bytecode = True
from atomic_replace import atomic_replace
from doctor import EXPECTED_QA, REQUIRED_TEX_FILES, _qa_versions
from font_paths import font_dir
ROOT = Path(__file__).resolve().parent.parent
EXTRA_TEX_FILES = ('luababel.def', 'babel-bidi-basic.lua', 'amstext.sty', 'mhsetup.sty')
COMMANDS = {'lualatex':['--version'], 'kpsewhich':['--version'],
            'pdfinfo':['-v'], 'pdftoppm':['-v']}


def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def run_command(argv: list[str]) -> str:
    result=subprocess.run(argv, capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise ValueError(f'{Path(argv[0]).name}: exit {result.returncode}')
    text=(result.stdout+'\n'+result.stderr).strip()
    if not text: raise ValueError(f'{Path(argv[0]).name}: empty output')
    return text


def collect() -> dict:
    errors=[]
    versions,qa_errors=_qa_versions(); errors.extend(qa_errors)
    for name,expected in EXPECTED_QA.items():
        if versions.get(name)!=expected:
            errors.append(f'{name}: installed {versions.get(name)!r}, validated baseline {expected}')
    if sys.version_info < (3,10): errors.append('Python 3.10+ is required')
    report={'schema':1,'skill_version':(ROOT/'VERSION').read_text().strip(),
            'scope':'required-build-dependencies',
            'platform':{'system':platform.system(),'release':platform.release(),
                        'machine':platform.machine(),'python':platform.python_version()},
            'qa':{'installed':versions,'validated_baseline':EXPECTED_QA.copy()},
            'skill_files':{name:digest(ROOT/name) for name in
                           ['assets/preamble.tex','scripts/build.sh','requirements-qa.txt','assets/fonts/SHA256SUMS']},
            'commands':{},'tex_files':{},'fonts_verified':False}
    for name,args in COMMANDS.items():
        executable=shutil.which(name)
        if not executable:
            errors.append(f'required command missing: {name}');continue
        try:
            text=run_command([executable,*args])
            report['commands'][name]={'version_lines':text.splitlines()[:2],
                                      'binary_sha256':digest(Path(executable))}
        except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
            # Do not serialize command arguments / absolute paths or arbitrary stdout.
            errors.append(f'{name}: {type(exc).__name__}')
    kpse=shutil.which('kpsewhich')
    if kpse and 'kpsewhich' in report['commands']:
        for name in (*REQUIRED_TEX_FILES,*EXTRA_TEX_FILES):
            try:
                result=run_command([kpse,name])
                paths=result.splitlines()
                if len(paths)!=1: raise ValueError('ambiguous dependency path')
                p=Path(paths[0]);report['tex_files'][name]={'sha256':digest(p),'size':p.stat().st_size}
            except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
                errors.append(f'TeX dependency {name}: {type(exc).__name__}')
    try:
        run_command([sys.executable,str(ROOT/'scripts/verify_font_bundle.py'),str(font_dir())])
        report['fonts_verified']=True
    except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
        errors.append(f'font verification: {type(exc).__name__}')
    report['errors']=errors;report['status']='complete' if not errors else 'incomplete'
    payload=json.dumps(report,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    report['fingerprint_sha256']=hashlib.sha256(payload).hexdigest()
    return report


def publish(report: dict, output: Path) -> None:
    """Atomic file replacement, not symlink-target writing; parent must exist."""
    data=json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+'\n'
    with tempfile.TemporaryDirectory(prefix='hllpdf-environment-') as td:
        source=Path(td)/'report.json';source.write_text(data,encoding='utf-8')
        atomic_replace(source,output)


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='JSON output path; omit to print JSON on stdout')
    args=parser.parse_args(argv)
    try:
        report=collect()
        if args.output:
            publish(report,args.output)
            print(f"{report['status']}: {args.output}; {len(report['errors'])} error(s)",file=sys.stderr)
        else: print(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2))
    except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
        print(f'environment report failed: {type(exc).__name__}: {exc}',file=sys.stderr);return 2
    return 0 if report['status']=='complete' else 1


if __name__=='__main__': raise SystemExit(main())

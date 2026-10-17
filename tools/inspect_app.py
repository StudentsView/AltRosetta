"""Read-only app metadata inventory. Does not read activation records or documents."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

from .macho import MAGICS, MachOError, parse_macho

PLIST_FIELDS = ('CFBundleIdentifier', 'CFBundleExecutable', 'CFBundleName',
                'CFBundleShortVersionString', 'CFBundleVersion', 'LSMinimumSystemVersion')


def _metadata(command, app):
    run = subprocess.run(command, capture_output=True, text=True, timeout=60)
    text = (run.stdout + run.stderr).replace(str(app), '$APP')
    return {'exit_code': run.returncode, 'text': text.strip()}


def _traversal_error(error):
    raise error


def _categories(symbols):
    return dict(Counter(
        'objc' if s.startswith(('_objc_', '_OBJC_')) else
        'cxx_exception' if s.startswith(('___cxa_', '__Unwind')) else
        'block' if s.startswith(('__Block', '__NSConcrete')) else 'other' for s in symbols))


def inspect_app(path: Path, apple_tools: bool = False) -> dict:
    app = Path(path).resolve(strict=True)
    plist = app / 'Contents' / 'Info.plist'
    if not app.is_dir() or not plist.is_file() or any(p.is_symlink() for p in (app / 'Contents', plist)):
        raise ValueError('expected an app with a regular Contents/Info.plist')
    info = plistlib.loads(plist.read_bytes())
    result = dict(schema_version=1, app_name=app.name,
                  bundle={k: info[k] for k in PLIST_FIELDS if k in info},
                  binaries=[], errors=[], kernel_extensions=[], driver_extensions=[])
    for directory, dirs, files in os.walk(app, followlinks=False, onerror=_traversal_error):
        base = Path(directory)
        dirs[:] = sorted(d for d in dirs if not (base / d).is_symlink())
        for d in dirs:
            relative = str((base / d).relative_to(app))
            if d.endswith('.kext'):
                result['kernel_extensions'].append(relative)
            elif d.endswith('.dext'):
                result['driver_extensions'].append(relative)
        for name in sorted(files):
            f = base / name
            if f.is_symlink() or not f.is_file():
                continue
            with f.open('rb') as stream:
                if stream.read(4) not in MAGICS:
                    continue
                stream.seek(0)
                data = stream.read()
            relative = str(f.relative_to(app))
            try:
                slices = parse_macho(data)
            except MachOError as error:
                result['errors'].append(dict(path=relative, error=str(error)))
                continue
            binary = dict(path=relative, size=len(data), sha256=hashlib.sha256(data).hexdigest(), slices=slices)
            if apple_tools:
                binary['signature'] = _metadata(['codesign', '-dv', '--verbose=2', str(f)], app)
                all_symbols = set()
                for s in slices:
                    nm = subprocess.run(['xcrun', 'nm', '-arch', s['architecture'], '-u', str(f)],
                                        capture_output=True, text=True, timeout=60)
                    if nm.returncode == 0:
                        symbols = sorted(set(nm.stdout.splitlines()))
                        s['undefined_symbols'] = symbols
                        s['import_categories'] = _categories(symbols)
                        all_symbols.update(symbols)
                    else:
                        s['symbol_error'] = nm.stderr.strip().replace(str(app), '$APP')
                binary['undefined_symbols'] = sorted(all_symbols)
                binary['import_categories'] = _categories(binary['undefined_symbols'])
            result['binaries'].append(binary)
    counts = Counter(s['architecture'] for b in result['binaries'] for s in b['slices'])
    result['summary'] = dict(binary_count=len(result['binaries']), architecture_slice_counts=dict(counts),
                             parse_error_count=len(result['errors']))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', type=Path)
    parser.add_argument('--apple-tools', action='store_true', help='include codesign and undefined import metadata')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = inspect_app(args.app, args.apple_tools)
        output = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding='utf-8')
            print(json.dumps(result['summary'], ensure_ascii=False))
        else:
            print(output, end='')
        return 1 if result['errors'] else 0
    except (OSError, ValueError, plistlib.InvalidFileException, subprocess.TimeoutExpired) as error:
        print(f'inspection failed: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

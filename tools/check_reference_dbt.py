"""Check a separately built alt-rosetta checkout against its small test contracts."""
import argparse
import json
from pathlib import Path
import subprocess

from .macho import parse_macho

CONTRACTS = {
    'test_exit': (42, ''), 'test_hello': (0, 'Hello\n'),
    'test_arithmetic': (0, 'PASS\n'), 'test_control_flow': (0, 'PASS\n'),
    'test_flags': (0, 'PASS\n'), 'test_fibonacci': (55, ''),
    'test_memory': (0, 'PASS\n'), 'test_syscall': (0, 'syscall test\n'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout', type=Path)
    args = parser.parse_args()
    root = args.checkout.resolve(strict=True)
    translator = root / 'build' / 'alt-rosetta'
    slices = parse_macho(translator.read_bytes())
    if len(slices) != 1 or slices[0]['architecture'] != 'arm64':
        parser.error('reference translator must be a thin ARM64 executable')
    results = []
    for name, (code, stdout) in CONTRACTS.items():
        # Only the ARM64 translator is executed. x86_64 paths are data arguments.
        try:
            run = subprocess.run([str(translator), str(root / 'build/tests' / name)],
                                 capture_output=True, text=True, timeout=10)
            passed = run.returncode == code and run.stdout == stdout
            if name == 'test_syscall':
                passed = passed and 'stderr ok\n' in run.stderr
            result = dict(name=name, passed=passed, exit_code=run.returncode,
                          stdout=run.stdout, stderr=run.stderr)
        except subprocess.TimeoutExpired:
            result = dict(name=name, passed=False, timeout_seconds=10)
        results.append(result)
    print(json.dumps({'tests': results, 'passed': sum(r['passed'] for r in results)}, indent=2))
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())

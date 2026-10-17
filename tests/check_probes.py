"""Check native JIT JSON and inspect the Intel fixture; never execute Intel code."""
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.macho import parse_macho

probe, fixture = sys.argv[1:]
result = json.loads(subprocess.check_output([probe], text=True))
assert result['architecture'] == 'arm64', result
assert result['translated'] is False, result
assert result['jit_returns'] == [42, 7], result
assert result['host_page_size'] >= 4096, result
slices = parse_macho(Path(fixture).read_bytes())
assert len(slices) == 1 and slices[0]['architecture'] == 'x86_64', slices
assert slices[0]['entrypoint'] is not None, slices
assert slices[0]['dependencies'] == [], slices
print(json.dumps(result, indent=2))

# Dual-Mac validation plan — 2013 Intel i5 ↔ 2026 Apple Silicon M5

- Created: 2026-10-14 (Asia/Seoul)
- Status: **PROPOSED; no new fixtures have been built or run on either user's Mac**
- Purpose: build a deterministic, progressively harder **project-owned x86_64-only** test suite to measure Rosetta-independent AltRunner/MacBridge progress.
- Existing research: [AGENTS](../../AGENTS.md), [FEASIBILITY](../FEASIBILITY.md), [ROADMAP](../ROADMAP.md), [ARCHITECTURE](../ARCHITECTURE.md), [ADR-001](../adr/001-cpu-engine.md).
- Scope: **MacBridge**. WinBridge and LinuxBridge may reuse result-schema, but PE/ELF guest ABI and runtime are separate.

## 1. Non-negotiable truth labels

**Do not conflate any of the following:**

1. `HOST_ARM64_JIT` — native ARM64 emits and runs ARM64 code. **Already demonstrated** in `experiments/jit_probe.cpp` (ad-hoc signature, not hardened release). Not x86 emulation.
2. `GUEST_X86_DBT` — native ARM64-host translator consumes raw x86_64 guest machine code and executes it (FEXCore Darwin spike); x86 state is verified. **Not demonstrated by AltRosetta**.
3. `MACHO_STATIC` — guest x86_64 Mach-O is loaded/entered by AltRunner without macOS executing it as a Rosetta process. **Not demonstrated**.
4. `DARWIN_DYNAMIC` — guest x86_64 imports/libSystem, guest↔host ABI, callbacks/dylibs functional. **Not demonstrated**.
5. `COCOA_GUI` — own Intel ObjC/Cocoa fixture opens a window and handles input/events. **Not demonstrated**.
6. `HWP_FUNCTIONAL` — legitimately licensed HWP runs, edits/saves/reopens/prints/PDFs, with untouched app and activation. **Not demonstrated**.

Reference Rosetta 2 **success is not AltRosetta success**. Compiling x86_64 on M5 or launching a direct Intel Mach-O through Rosetta 2 does **not** test the AltRunner translation engine.

## 2. Two machine roles and environment inventory

**2013 MacBook Air Intel i5 = Reference A (native x86_64 golden baseline).**
Apple officially supports macOS Big Sur on MacBook Air 2013; do **not** assume which macOS/Xcode is actually installed. Modern Xcode may not install; M5 can cross-compile `x86_64` fixtures for an appropriately chosen minimum deployment target. Build **one immutable x86_64 artifact** and transfer exactly those bytes for per-machine test, never compare different machine-local builds without versioning.

**2026 MacBook Air M5 = Reference B (Apple Rosetta 2, where still supported) and target C (AltRunner native ARM64).**
Rosetta 2 is the reference only; AltRunner must itself be **arm64 only**, explicitly record `sysctl.proc_translated == 0` for the host runner and load x86_64 guest bytes as **data** into its own translation/loader route. Running `arch -x86_64 fixture` invokes Apple translation — not AltRunner.

**Inventory record (both machines, user performs locally):**
```sh
sw_vers
uname -m
sysctl -n hw.pagesize
xcode-select -p
xcrun --find clang
xcrun clang --version
xcrun --show-sdk-version
```
Record model identifier (`sysctl -n hw.model`), CPU, arch, OS build, Xcode/CommandLineTools version, page size, and available disk/RAM. **Never publish machine serial numbers, user paths, Apple ID, or license data**.

**Build matrix:**
- Canonical fixture source, compiler flags, exact binary SHA-256, SDK/build tools and deployment target always recorded. Use `clang -arch x86_64 -mmacosx-version-min=<reference-machine-os-compatible-target>`; select exact target after `sw_vers` of Intel host.
- For early raw x86 instruction cases, package machine-code bytes and expected registers; an Intel-native x86_64 test harness invokes the **same instruction bodies** to generate golden results. These are **not OS-launchable Mach-O files**.
- For dynamic C/ObjC fixtures, compile x86_64-only Mach-O compatible with both hosts if possible; avoid APIs absent on the older Intel macOS. The M5 reference baseline can differ because OS/framework versions differ. Record and triage as `OS_DIFFERENCE`, not automatically a translation bug.
- For minimal `-nostdlib` Mach-O from existing repository, do **not** assume standalone native macOS execution is possible; existing FEASIBILITY notes `libSystem` linker requirements and a `-static -nostdlib` fixture. Golden `LC_UNIXTHREAD` entry behavior can be checked via a native x86 test harness and explicit loader contract.
- Rosetta baseline on M5 where supported: same *dynamic* Intel fixture and input under the system translator. Later macOS 28 may not run those apps: retain historical baseline and explicitly label stale.

## 3. Fixture ladder (one primary failure class per case)

| Tier/ID | Own fixture | Primary assertions | Intel golden route | M5 AltRunner gate |
|---|---|---|---|---|
| J0 `NATIVE-JIT-00` | Existing ARM64 `jit_probe` | MAP_JIT/W^X, returned 42 & 7, host arch arm64 | N/A | Already observed in ad-hoc unsigned release context only |
| J1 `RAW-01` | raw x86_64 MOV RAX,42; RET | guest RAX==42, guest PC+RSP, clean guest return | x86-native harness on Intel | FEXCore Darwin init, IR/back-end, result |
| J1 `RAW-02` | ADD/SUB/XOR/CMP/Jcc loop | flags CF/ZF/SF/OF, loop exits, deterministic reg snapshot | x86-native harness | no host-side interpreter shortcut |
| J1 `RAW-03` | x86 stack/call/RET and guest memory | guest stack/state/memory unchanged outside allowed range | x86-native harness | guest↔host address separation |
| J1 `RAW-04` | SSE2 vectors, then feature-gated AVX/AVX2 | lane values, MXCSR, feature/CPUID policy | x86-native harness if hardware supports each ISA | vector translation; AVX512 excluded |
| J1 `RAW-05` | guest memory pages, page perms, atomics | 4KB guest semantics on potentially 16KB host, OOB guard, TSO cases | x86-native harness | safe mapping, no MAP_FIXED overwrite |
| J2 `MACHO-01` | self-authored minimal x86_64 static Mach-O, entry/exit convention | segment layout, LC_MAIN/LC_UNIXTHREAD, register result 42 | structural gold + x86 native harness (not necessarily standalone launchable) | own loader + x86 CPU execution |
| J3 `DARWIN-01` | x86_64 C CLI prints fixed bytes and returns code | stdout bytes, stderr bytes, exit code, arguments/env | native launch on Intel; Rosetta on M5 | libSystem import + Darwin API bridge |
| J3 `DARWIN-02` | read-only temp fixture file, stat/open/read/close | data digest, errno, file descriptor behavior | native + Rosetta | sandbox-granted file IO only |
| J3 `DYLD-01` | x86_64 dylib import / function pointer / callback | symbol binding, initializer order, guest→host→guest callback | native + Rosetta | guest dynamic binding/ABI |
| J3 `ABI-01` | structs, float/double, varargs, blocks, TLS, optional C++ exceptions | byte-accurate aggregate/fp/stack, callback, unwind | native + Rosetta | x86 guest/ARM host ABI bridge |
| J3 `THREAD-01` | two/4 workers, atomics, mutex/cond, signals | deterministic post-join sums + event ordering constraints | native + Rosetta | TSO, guest pthread, fault delivery |
| J4 `OBJC-01` | x86_64 Foundation-only CLI | class/selector/IMP, +load, autorelease, object lifetime | native + Rosetta | ObjC runtime bridge |
| J4 `COCOA-01` | x86_64 NSApplication/NSWindow app | window appears, event callback, menu, close, no host crash | native + Rosetta | host AppKit equivalence |
| J4 `COCOA-02` | own Unicode/Hangul document editor | Korean IME composition, file open/save/reopen, CoreText/PDF hash/canonical checks | native + Rosetta | HWP preconditions, no real documents |
| J5 `HWP-01` | original legally-owned Hancom app, own empty doc only | launch, blank doc, edit/IME, save/reopen, PDF, normal authorization path | supported host reference and/or Rosetta only | **only after J4 gates**, NEVER modify original app |

**Important:** RAW fixture code can be used on Intel only via the native reference harness; do not require the M5 to invoke x86 code outside AltRunner. More numerous CPU instructions can be added as **orthogonal ISA regression set** after `RAW-01`; the OS layers must not become prerequisites for raw opcode tests.

## 4. Exact 3-lane comparison

```text
canonical repo-owned fixture sources + pinned compiler
               |
     byte-for-byte x86_64 target
               |
       SHA-256 + provenance
          /         |             \
2013 Intel       2026 M5      2026 M5
native x86       Rosetta2      AltRunner arm64
    |                |           (guest x86 bytes)
reference A      reference B       target C
    \                |            /
        normalized result comparison
```

**Example CLI conventions (PROPOSED, NOT IMPLEMENTED):**
```sh
# Reference A, only for OS-launchable x86 Mach-O fixtures:
./build/x86_64/DARWIN-01 --seed 42 --report reports/local/intel/DARWIN-01.json

# Reference B (macOS versions supporting Rosetta):
arch -x86_64 ./build/x86_64/DARWIN-01 --seed 42 --report reports/local/rosetta/DARWIN-01.json

# Target C (M5 arm64 native host, explicitly NOT arch -x86_64):
./build/arm64/alt-runtime-probe --guest build/x86_64/DARWIN-01 \
  --seed 42 --report reports/local/alt-runner/DARWIN-01.json
```

For raw guest opcode tests use `x86-native-harness` on 2013 Intel for reference A; for Rosetta reference B use the x86-native harness under Apple Rosetta (not stand-alone raw code); for target C pass the byte buffer to `alt-runtime-probe`. Proposed harness should support `--list`, `--test-id`, `--seed`, `--report`, `--timeout-seconds`.

**Proof of no Apple Rosetta in C:**
- AltRunner host binary is arm64-only (check `file`, `lipo -archs` and codesign entitlement metadata).
- AltRunner host process returns `sysctl.proc_translated=0` (Apple documented; on Intel sysctl may be absent; distinguish absent from error).
- Program loads the x86 fixture as **guest bytes**, invoking FEX adapter through the ARM64 execution process. No `execve`, `posix_spawn`, `arch -x86_64`, Rosetta oah service, or native `dlopen` of guest x86 Mach-O in the C path. Prove by code review and process tree.
- Native status alone is **necessary but insufficient**: host could launch a different x86 child under Rosetta. Therefore inspect guest launch implementation and native process family.

**Minimum result JSON (not logs containing user secrets):**
```json
{
  "schemaVersion": 1,
  "fixtureId": "RAW-01",
  "fixtureSha256": "<hash>",
  "lane": "intel_native | apple_rosetta | altrosetta_arm64",
  "runtimeVersion": "<commit>",
  "hostMachineClass": "2013-intel | 2026-m5",
  "hostOS": "<version/build>",
  "hostArch": "x86_64 | arm64",
  "hostPageSize": 16384,
  "hostTranslated": false,
  "compilerId": "<version>",
  "compilerFlags": ["<target>"],
  "inputSeed": 42,
  "outcome": "PASS | FAIL | BLOCKED | CRASH | TIMEOUT | NOT_RUN",
  "stdoutHex": "34320a",
  "stderrHex": "",
  "exitCode": 0,
  "guestRegisters": {"RAX": 42},
  "memorySha256": "<hash-or-null>",
  "elapsedMs": 0,
  "crashKind": null
}
```
Do not blindly demand identical memory addresses, PID, time, process architecture, or OS-generated messages across hosts. For GUI use state/event/UTF-8 and normalized document semantics rather than pixel-level screenshot equality. For non-deterministic concurrent programs define allowable outcomes/invariants and stress seeds; capture ordering trace for diagnosis.

## 5. Failure triage taxonomy

- `BUILD_ERROR`: legacy deployment SDK/ABI issue, no runtime claim.
- `INSPECTOR_ERROR`: invalid Mach-O/header; parser problem.
- `TRANSLATOR_ERROR`: x86 decode/IR/ARM64 JIT or register mismatch in RAW.
- `MEMORY_MODEL_ERROR`: guest VA/page guard/TSO/atomics.
- `LOADER_ERROR`: segment/ASLR/LC_MAIN/LC_UNIXTHREAD/TLS/binding.
- `ABI_ERROR`: guest↔host parameter/struct/stret/varargs/exception.
- `DARWIN_API_ERROR`: x86 syscall/libSystem compatibility.
- `OBJC_OR_GUI_ERROR`: ObjC/AppKit/IME/window callback.
- `OS_DIFFERENCE`: Big Sur vs M5 macOS APIs/behavior; compare Reference B.
- `POLICY_DENIED`: correct security block (do not mark failure).
- `CRASH`/`TIMEOUT`/`LIMIT_EXCEEDED`: worker isolated/fail-closed; do not panic host.

**Result claim threshold**: do not call a tier complete until deterministic required cases pass on both native Intel (or justified structural gold) and the M5 AltRunner lane, including **negative inputs and restart/crash tests**. Apple Rosetta lane is optional reference when macOS supports it and meaningful for OS dynamic fixtures.

## 6. Safety and machine protection

- Only project-authored fixtures until J4. No proprietary HWP, installer, or personal document stored in GitHub/Notion or uploaded to third-party AV.
- No `sudo`, SIP/AMFI changes, `kmutil`, `kextload`, driver installation, kernel experiments, root helper, identity/activation access, or shell execution from package scripts.
- Development first in **separate unprivileged process** with no write grants beyond a disposable sandbox directory. No host kernel panic experiment on user's machines.
- JIT runtime limits: timeout (initial small deterministic sample), process memory cap (validated per platform), byte count/snapshot cap, crash-loop breaker; on error worker terminates and records `CRASH` or `TIMEOUT`, not `PASS`.
- No `MAP_FIXED` replacement of live host mappings; use safe address reservation and translation.
- Temp results and raw crash data live in `reports/local/` (Git-ignored). Redact user paths, usernames, serial numbers.
- Stage a later malformed bytecode and malformed Mach-O corpus only through restricted parser/runtime workers and preferably disposable isolated test machine; avoid dangerous kernel or driver tests.
- Run unit tests + native probe before merge; never auto-run untrusted guest on a production user document.

## 7. Minimal first Codex PR (NO implementation is claimed yet)

Create a **new feature branch**, independent of open AltInstaller Issue #8, and do not change old tests or current `HwpMac2014.app`.

Deliverables:
1. `tests/fixtures/guest_x86_64/RAW-01.s`, `RAW-02.s`, `RAW-03.s` and stable manifest `cases.json` (initially few cases, not entire ladder).
2. `tools/build_guest_fixtures.py`: deterministically assemble/link x86 fixture data, report SHA-256/toolchain; do not require 2013 host to install newest Xcode.
3. `tests/reference/x86_native_harness.c` (or C++): compiled Intel-only; invokes the **same x86 instruction bodies** as project raw guest fixture to record registers/flags/return, with safe bounds.
4. `tools/compare_runtime_results.py`: verify matching fixture ID/hash/input, normalize deterministic fields, fail CI with clear mismatch classifications. First use **synthetic report JSON** fixtures; do not require successful FEX integration just to test the comparator.
5. `docs/testing/README.md`: exact 2013/M5 shell commands, result record format, supported OS versions, Not-run and expected-fail handling, privacy warning.
6. Extend FEXCore Darwin spike (separate PR after harness schema) to route the **identical RAW-01 bytes** through `AltFEXAdapter` and capture guest `RAX=42`.
7. Add minimal x86 Mach-O fixture J2 **only after J1 passes**.
8. CI: parser/manifest/comparator checks on Linux/any host; Intel native execution only on user's 2013 Intel; ARM64 core/JIT only on user's M5 Mac or dedicated ARM64 macOS runner. Never claim tests that were not run.

**Acceptance for first PR:** sources+manifests self-owned; identical hash across transferred machines; Intel native RAW-01/02/03 baseline collected on hardware (unless not yet run, then mark BLOCKED/NOT_RUN); comparator tests pass; results do not assert AltRunner x86 support until `AltFEXAdapter` actually executes guest bytes; all repo unit tests remain passing.

## 8. First data request from user (only when running on hardware)

Ask for **`sw_vers`, `uname -m`, `xcode-select -p`, `xcrun clang --version`, `sysctl -n hw.pagesize`** from both Mac machines and confirmation of physical build model and Rosetta baseline availability. Do not request personal identifiers. The 2013 MacBook Air's *installed* macOS matters more than its release year for selecting compile target.

## 9. References

- [Apple macOS Big Sur Mac compatibility (2013 MacBook Air supported)](https://support.apple.com/ko-kr/111980)
- [Apple Rosetta process detection `sysctl.proc_translated`](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment)
- [Apple Intel Rosetta general support last in macOS 27](https://developer.apple.com/news/?id=w5ngl9k2)
- [Apple Universal Binary build and architectures](https://developer.apple.com/documentation/apple-silicon/building-a-universal-macos-binary)
- [AltRosetta FEXCore feasibility evidence](../FEASIBILITY.md)

# Phase 0 기술 조사 및 실험 기록

조사일: 2026-10-13 (Asia/Seoul). 아래의 확인됨/미확인은 이번 세션의 증거 범위다.
기존 Chat 기획의 사실 주장을 그대로 확정하지 않고 실제 소스와 설치본을 확인했다.

## 출처와 고정 ref

- [Apple, 2026-09-01 Rosetta 공지](https://developer.apple.com/news/?id=w5ngl9k2):
  macOS 27이 일반 Rosetta 지원의 마지막 버전이라는 기획 전제를 재확인했다.
  오래된 일부 게임에 대한 예외는 사무용 앱의 향후 지원 보장이 아니다.
- [FEX](https://github.com/FEX-Emu/FEX/tree/fb925d6fc5cc8576bf0f9ae6978fc6d912485593):
  `fb925d6fc5cc8576bf0f9ae6978fc6d912485593`.
- [Hadron](https://github.com/Broyojo/hadron/tree/142140abad3c5e53a09dc1f9cd919a9722d1fa00):
  `142140abad3c5e53a09dc1f9cd919a9722d1fa00`.
  해당 `sources.conf`의 FEX pin은 `0df84d3844bcdb87bb7d3f5b8fb0959cd009c038`이다.
  이번 upstream FEX snapshot과 다르므로 Hadron patch가 최신 snapshot에 적용된다고 가정하지 않는다.
- [alt-rosetta](https://github.com/sadopc/alt-rosetta/tree/5699299be6ebb85436fb5e5c39c37267964fda18):
  `5699299be6ebb85436fb5e5c39c37267964fda18`.
- [Apple JIT 안내](https://developer.apple.com/documentation/apple-silicon/porting-just-in-time-compilers-to-apple-silicon).
- [Apple Rosetta 환경](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment).

## FEX / Hadron: 확인된 소스와 첫 configure

FEX `CMakeLists.txt:64-67`은 Darwin을 명시적으로 거부한다.
현재 snapshot에 다음 명령을 실제로 실행했고 `Unsupported system type Darwin.
FEX only supports Linux and Windows.`로 설정이 중단됐다.

```sh
.venv/bin/cmake -S .local/upstreams/FEX -B build/fex-upstream -G Ninja \
  -DCMAKE_MAKE_PROGRAM="$PWD/.venv/bin/ninja" \
  -DCMAKE_C_COMPILER=/usr/bin/clang -DCMAKE_CXX_COMPILER=/usr/bin/clang++ \
  -DBUILD_TESTING=OFF -DENABLE_LTO=OFF -DENABLE_JEMALLOC_GLIBC_ALLOC=OFF
```

이는 platform guard 확인이며 FEXCore 이식이 불가능하다는 증거가 아니다.
아직 FEXCore 컴파일, context 초기화, x86 instruction 실행은 하지 못했다.
submodule은 재귀 다운로드하지 않았고 Linux frontend를 빌드하지 않았다.

Hadron `scripts/build-fex.sh`는 llvm-mingw로 ARM64EC/WoW64 **Windows PE DLL**을
만들고 별도의 Darwin unix helper를 만든다. 따라서 Hadron이 Mac에서 Windows 앱을
실행하는 것과 AltRosetta가 Mac Mach-O 앱을 실행하는 것은 다른 문제다.

`patches/fex/0001`은 Darwin unix helper 변경, `0002/0003`은 64KB guard,
`0004`는 x86 compatibility mode, `0005`는 JIT allocator/write-protect hook을 다룬다.
코드 재사용 후보 지점은 확보했으나 native Darwin 코어로 결합하지 않았다.

FEX 최상위 라이선스는 MIT, Hadron 최상위는 `LICENSE.hadron`의 BSD-3-Clause이며
patch/component는 각각 원본 라이선스를 따른다. 이 저장소에 upstream 코드를 복사하지 않았다.

## 자체 ARM64 JIT: 확인됨

환경: ARM64, macOS 27.2 build 26B5101f, Xcode 27.1 build 27A9275,
Apple Clang 21.0.0, SDK 27.0, Python 3.14.3, CMake 4.4.4, Ninja 1.13.2.
Python venv와 CMake/Ninja는 `.venv/`에 준비했다.

`experiments/jit_probe.cpp`를 native arm64로 빌드하여 실행했다.
서명은 linker가 만든 ad-hoc, hardened runtime flags 없음, entitlement 설정 없음이다.
실행 결과:

```json
{"architecture":"arm64","translated":false,"host_page_size":16384,"jit_write_protection":true,"cross_arch_kernel_support":true,"jit_returns":[42,7]}
```

`MAP_JIT` → per-thread write enable → ARM64 instructions 기록 → write protect →
instruction cache 갱신 → 실행을 확인했다. 같은 buffer를 바꿔 두 반환값을 확인했다.
이 결과는 우리 JIT substrate만 검증한다. x86 decoder, FEX, Mach-O loader 또는
배포 signing에 대한 검증은 아니다.

SDK의 `usr/include/os/arch/arm64.h`에는 `os_cross_arch_is_supported`가 macOS 26.6+
API로 선언돼 있으며 커널 기능 존재만 보고한다고 명시돼 있다. 이 Mac에서 true였지만
cross-architecture entitlement/profile 발급·적용은 확인하지 않았다.
[Hadron 계정 설정 문서](https://github.com/Broyojo/hadron/blob/142140abad3c5e53a09dc1f9cd919a9722d1fa00/docs/apple-developer-setup.md)의
포털 capability 설명은 프로젝트 저자의 기록이다. 우리 계정에서의 가능 여부 및
macOS 28 이후 유지 여부는 미확인이다.

## 자체 Intel fixture: 빌드와 조사만 확인됨

Apple linker는 `-nostdlib`의 dynamic executable에 libSystem을 요구했다.
따라서 `-static -nostdlib`의 자체 `_main` fixture로 범위를 정리했다.
`LC_UNIXTHREAD`의 x86_64 RIP entrypoint를 추가로 조사한다. 향후 guest runtime은
RET의 종료 convention을 제공해야 한다. 이 파일을 macOS가 직접 실행하지 않았다.

## 외부 alt-rosetta: 작은 번역 테스트 결과

별도 ignored checkout에서 `make all tests`가 성공했다. translator 실행 파일의
Mach-O는 **arm64**임을 확인했다. 각 Intel fixture는 직접 실행하지 않고 native
translator에 인수로 전달했다. 각 프로세스에 10초 제한을 뒀다.

8개 테스트의 exit code 및 stdout 계약이 모두 일치했다:
exit(42), hello, arithmetic, control_flow, flags, fibonacci(55), memory, syscall.
syscall의 stderr에 `stderr ok`도 관찰했다.
단, memory 테스트는 성공 결과와 함께 `movsxd ...` translation failure warning을
출력했다. 따라서 전체 instruction 정확성을 검증했다고 해석하지 않는다.

upstream의 shell harness는 `stdout=$(...) || true` 뒤의 `$?`로 exit code를
수집하므로 원래 실패 코드를 잃을 수 있고, `set -e` + `((passed++))`로 첫 성공에도
중단될 수 있다. 이를 사용하지 않고 Python `subprocess.run`의 returncode와 stdout을
직접 확인했다. 재현 도구는 `tools/check_reference_dbt.py`이다.

이 프로젝트의 README에는 dynamic linking, SSE/AVX, threading, guest signal forwarding,
TSO 등이 미구현으로 명시된다. 라이선스는 README의 비표준 `Use as you wish` 문구다.
정식 라이선스 확인 전 코드를 프로젝트에 통합하지 않는다. 한글 실행 엔진의 채택 근거가
아닌 최소 native DBT 가능성의 외부 참고 결과다.

## 도구 검증

Python unittest 14개 및 CTest 2개 그룹이 로컬에서 통과했다. 테스트에는 thin/fat
헤더, 손상 command/offset, static entrypoint, symlink, 접근 불가 디렉터리,
아키텍처마다 다른 import를 갖는 자체 Universal object fixture가 포함된다.
네이티브 통합 테스트는 JIT 결과와 Intel fixture 메타데이터를 확인한다.
Linux CI에서는 Apple tool 통합 테스트 1개를 건너뛰고 나머지 parser/번들 검사를 실행한다.

최종 코드 리뷰에서 Universal 바이너리의 기본 nm가 ARM64만 조사하는 문제와
os.walk가 접근 불가 디렉터리를 조용히 누락하는 문제를 발견했다. 각각 실패하는
회귀 테스트를 추가한 후 아키텍처 명시와 traversal 오류 전파로 수정했다.

## 아직 답하지 못한 것

FEXCore Darwin 포트, 실제 preferred-address mapping, guest syscall/exception/TLS,
dyld rebasing/binding/initializers, ObjC runtime 등록, host↔guest callbacks, C++ unwinding,
한글 IME/편집/저장/PDF/인증, 배포 signing, macOS 28 호환성은 모두 미검증이다.
한글을 실행하거나 실제 문서를 열지는 않았다. pkg 없이 번들 구조 조사는 가능했다.

# AltRosetta

Apple Silicon Mac에서 Intel 전용 macOS 사무용 앱을 Rosetta 없이 실행할 수 있는지
검증하는 프로젝트입니다. 첫 대상은 사용자가 보유한 한글 2014 VP for Mac입니다.

**현재 단계: Phase 0, 비공개 기술 조사.** 앱 실행기나 CPU 번역기는 아직 없습니다.
현재 동작하는 결과물은 Mach-O/앱 조사 도구, ARM64 JIT 검증, 자체 Intel fixture입니다.

## 시작하기

조사 도구는 Python 3.11 이상만 필요합니다. 네이티브 실험은 Apple Silicon macOS와
Xcode가 필요합니다. 이번 검증 환경은 macOS 27.2, Xcode 27.1 / SDK 27.0입니다.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v

.venv/bin/python -m tools.inspect_app /Applications/HwpMac2014.app \
  --apple-tools --output reports/local/hwp.json

.venv/bin/cmake -S . -B build/phase0 -G Ninja \
  -DCMAKE_MAKE_PROGRAM="$PWD/.venv/bin/ninja" \
  -DPython3_EXECUTABLE="$PWD/.venv/bin/python"
.venv/bin/cmake --build build/phase0
.venv/bin/ctest --test-dir build/phase0 --output-on-failure
```

`--apple-tools`는 macOS의 `codesign`, `xcrun nm`로 코드 서명 표시 정보와 undefined
symbol 이름을 수집합니다. 앱 실행, 인증 상태 조회, 인증 변경은 수행하지 않습니다.
raw 보고서, 개발 도구, upstream checkout 및 생성 바이너리는 Git에서 제외합니다.

JIT probe는 linker의 ad-hoc 서명을 사용한 개발용 실험입니다. 배포용 hardened runtime,
notarization, restricted entitlement는 검증하지 않았습니다. `cross_arch_kernel_support`
값은 커널 기능 존재 여부이며, 앱의 entitlement 발급이나 번역기 동작을 뜻하지 않습니다.

## 문서

- [설치된 한글의 실제 구조](docs/TARGET_HWP.md)
- [기술 조사와 검증 결과](docs/FEASIBILITY.md)
- [잠정 아키텍처](docs/ARCHITECTURE.md)
- [다음 검증 관문](docs/ROADMAP.md)
- [CPU 엔진 결정 기록](docs/adr/001-cpu-engine.md)
- [이번 작업의 설계](docs/superpowers/specs/2026-10-13-phase0-design.md)
- [구현 계획](docs/superpowers/plans/2026-10-13-phase0.md)
- [AltInstaller: PKG/EXE/MSI 설치 시스템 설계 (제안)](docs/ALTINSTALLER_DESIGN.md)
- [macOS·Windows·Linux 통합 전략 (제안)](docs/MULTI_OS_STRATEGY.md)
- [Codex 인계: 설치 분석기 우선 작업](docs/CODEX_HANDOFF_2026-10-13.md)
- [ADR-002: 악성코드 탐지·권한·드라이버 차단·크래시 복구](docs/adr/002-malware-safety.md)
- [ADR-003: AltRunner·AltInstaller·AltSecurity 3대 모듈 구조](docs/adr/003-three-pillar-architecture.md)
- [상세 보안 결정(비공개 Notion)](https://app.notion.com/p/3f8470a2491c813fa897cc04798476b5?pvs=204)

원본 코드의 라이선스는 MIT입니다. 상용 앱, 문서, 설치 파일은 포함하지 않습니다.
upstream 코드를 통합하는 경우 해당 저작권 및 라이선스를 별도로 유지해야 합니다.

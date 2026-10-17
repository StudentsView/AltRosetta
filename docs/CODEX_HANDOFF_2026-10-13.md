# Codex 인계: AltInstaller 읽기 전용 PKG Analyzer + WinContainer 설계

- 인계일: 2026-10-13
- 시작 브랜치: 기본 `main`의 현재 상태를 읽고 **별도 feature branch**에서 작업할 것
- 우선순위: P0 PKG analyzer. WinContainer는 후속 설계.
- 이 문서는 **작업 지시서**이며 구현/검증 완료를 뜻하지 않는다.

## 1. 먼저 읽을 것

1. [AGENTS.md](../AGENTS.md) — 상용 앱, 비공개 저장소, SIP/AMFI/정품 인증 등 안전 규칙.
2. [README.md](../README.md) — 현재 Phase 0 실험과 실행 방법.
3. [ARCHITECTURE.md](ARCHITECTURE.md) · [ROADMAP.md](ROADMAP.md) · [TARGET_HWP.md](TARGET_HWP.md) · [FEASIBILITY.md](FEASIBILITY.md).
4. [ALTINSTALLER_DESIGN.md](ALTINSTALLER_DESIGN.md) · [MULTI_OS_STRATEGY.md](MULTI_OS_STRATEGY.md).

**현재 실제 구현**은 Mach-O/앱 읽기 전용 inspector, ARM64 JIT probe, 자체 Intel fixture에 한정된다. MacBridge/WinBridge/LinuxBridge/AltInstaller는 완성된 도구가 아니다. 기존 FEXCore Darwin spike를 방해하거나 기존 코드를 대규모로 재구성하지 말 것.

## 2. 첫 PR 범위: `inspect_pkg` (P0)

**목표:** ARM64 macOS에서 Intel 앱이 들어 있는 flat `.pkg`를 **실행/설치 없이** 읽고, 설치에 필요한 정보와 차단 조건을 JSON으로 출력한다.

권장 CLI 예시(세부 문법은 기존 `tools.inspect_app` 패턴에 맞출 것):
```sh
python3 -m tools.inspect_pkg /path/to/package.pkg --output reports/local/pkg-analysis.json
```

### 필수 동작

- `pkgutil` 도구 존재 여부, 패키지 형식, 서명 검사 상태 및 검사 불가 원인을 보고.
- `pkgutil --payload-files`로 내부 경로 목록 확보; 필요 시 격리된 임시 위치에서 `--expand-full` 시도. 지원 여부를 런타임에서 검사.
- component `PackageInfo`, `Distribution`, payload 및 `preinstall/postinstall` 스크립트의 존재·참조를 조사.
- 포함 Mach-O 파일을 **실행하지 않고** 아키텍처(x86_64/arm64/universal) 분류.
- Intel-only 설치 helper, 권한 상승 필요 가능성, system path write, symlink/path traversal 같은 위험 신호를 구조화.
- 명령 실패/타임아웃/도구 부재에 대한 명시적 오류 기록. 임시 디렉터리 및 디스크 상한/압축 폭탄 위험 고려.
- 사용자가 지정한 결과 JSON 외에는 시스템/앱 상태를 변경하지 않는다.

### 명시적 비목표

- `installer`를 이용한 실제 설치, 원본 `preinstall/postinstall` 실행, DRM/서명 변경, 기존 `HwpMac2014.app` 수정.
- MacBridge/CPU 변환기 또는 Windows 설치 GUI를 구현했다고 주장.
- 사용자 보유 한글 설치 파일·문서·식별 가능한 경로/시리얼/인증 데이터 커밋.

### 테스트/완료 조건

- 자체 제작·재배포 가능한 테스트 `.pkg` 또는 명령 출력 fixture 사용(최소: 기본 flat package, nested components, Intel-only helper reference, malformed metadata, symlink/path traversal 시도, `pkgutil` 없음).
- 결과 스키마가 안정적이고 비정상 입력에서도 안전하게 실패할 것.
- `python3 -m unittest discover -s tests -v` 통과; Apple Silicon 네이티브 실험은 `cmake`/ `ctest` 규칙을 따를 것.
- 새로운 기능이 기존 앱 inspector와 기존 Phase 0 테스트를 깨지 않을 것.
- PR에는 실제 실행한 테스트, 샘플 JSON, **설치/앱 실행 미검증** 표시, 알려진 한계를 기재.

## 3. 후속 PR 범위: WinContainer 모델 (P1)

현재 단계는 **설계/단위 테스트만**. Wine 실행이 검증된 것처럼 주장하지 않는다.

- prefix 아래 `drive_c/`, `dosdevices/`, `system.reg`, `user.reg` 구조와 manifest 위치 결정.
- `C:\Program Files\...` Windows 경로를 해당 prefix 내부 host 경로로 매핑하는 **순수 로직** 및 테스트.
- 위험 매핑(`Z:`로 host 루트 접근 등)과 sandbox 한계 문서화.
- EXE와 MSI 원본 마법사 실행은 ARM64-host Wine + x86 변환 런타임 검증 후 별도 PR로 분리.
- 제거/업데이트/복구 시 사용자 파일 보존 정책 및 installState/launchState 구분.

## 4. 안전 불변 조건

- 기본 브랜치에 바로 검증되지 않은 실행/설치 기능을 추가하지 않는다. feature branch + PR.
- repo는 private. 상용 앱/설치 파일/비밀/정품 인증 기록 커밋 금지.
- SIP/AMFI 비활성화, 커널 변경, kext/드라이버, 활성화 우회 금지.
- 미확인 OS 호환성을 '성공'으로 표시하지 않는다.
- 기존 `docs/ROADMAP.md`의 MacBridge 주 연구 관문을 변경하지 않는다.

## 5. 작업 완료 보고 템플릿

- **구현 내용**:
- **실행 환경 (macOS, arch, Xcode)**:
- **테스트 결과 (정확한 명령/통과 수)**:
- **지원 범위와 미지원 형식**:
- **상용 패키지/실제 앱은 실행하지 않았음 여부**:
- **후속 차단 문제**:
- **PR URL / commit SHA**:

## 6. 관련 출처

- [macOS pkgutil 매뉴얼](https://keith.github.io/xcode-man-pages/pkgutil.1.html)
- [Apple Rosetta 지원 범위](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment)
- [WineHQ](https://www.winehq.org/)

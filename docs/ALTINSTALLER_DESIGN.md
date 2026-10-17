# AltInstaller 설계 명세 (초안)

- 작성: 2026-10-13
- 상태: **설계 제안 / 미구현**. 이 문서는 실행 호환성 검증 결과가 아니다.
- 범위: Apple Silicon macOS에서 Intel macOS PKG 및 Windows EXE/MSI 설치 처리
- 관련 문서: [ARCHITECTURE](ARCHITECTURE.md) · [ROADMAP](ROADMAP.md) · [멀티 OS 확장](MULTI_OS_STRATEGY.md) · [Codex 인계](CODEX_HANDOFF_2026-10-13.md)

## 0. 최우선 원칙

**설치 가능 ≠ 실행 가능.** 표준 macOS `.pkg`는 내부에 Intel용 앱이 포함되어 있어도 그 패키지 자체가 Intel 실행 파일인 것은 아니다. 기본 macOS 도구가 패키지 메타데이터를 읽을 수 있으나, 내부 x86_64 실행 보조 프로그램·스크립트가 성공한다는 뜻은 아니다. MacBridge는 아직 존재하지 않으며 macOS 28에서 Intel macOS 앱 실행이 가능하다고 주장하지 않는다.

현재 저장소의 원래 목적(한글 2014 VP for Mac을 비롯한 Intel Mac 사무용 앱의 독립적 실행 검증)을 유지한다. Windows/Linux 설치 지원은 **별도 런타임**이다.

## 1. AltInstaller 구성과 책임

```text
User-selected input (.pkg/.mpkg/.dmg/.app/.exe/.msi)
  -> TypeDetector (UTType, file signature, Mach-O/PE/ELF inspection)
  -> SourceVerifier (hash, signature, download provenance)
  -> InstallAnalyzer (metadata, actions, dependencies, payload & script inventory)
  -> InstallPlanner (target path map, policy, capabilities, conflict forecast)
  -> UserReview (unusual writes, install scripts, network, external helpers)
  -> Staging (isolated temporary location)
  -> Executor (macOS safe-copy path OR supported Wine runtime)
  -> Verify (expected files, manifests, supported launch target)
  -> AppRegistry (per-app installation metadata, log, uninstall ownership)
  -> Recovery Manager (best-effort rollback/restore)
```

동일한 UI/로깅/상태 머신을 공유하되 각 OS별 설치 행동을 공유 엔진으로 오인하지 않는다.

상태 머신: `DETECTED -> ANALYZED -> PLANNED -> APPROVED -> STAGED -> INSTALLING -> VERIFYING -> REGISTERED`. 실패 시 `FAILED`, 가능한 경우 `ROLLBACK_PENDING -> ROLLED_BACK`; 미지원 동작은 `BLOCKED_UNSUPPORTED`. UI에서 '파일 추출 완료', '설치 완료', '실행 검증 완료'를 구분한다.

## 2. macOS PKG: Rosetta 없이 읽기와 설치를 분리

### 2.1 지원 형식과 구분

- **flat `.pkg`**: `Distribution` 또는 `PackageInfo`, `Payload`, `Bom`, `Scripts` 등 구성 분석.
- **`.mpkg`/component bundle**: 하위 패키지·선택 항목·설치 순서·대상 볼륨/경로 정책 분석. 형식별 제한을 명시.
- **`.dmg`**: 우선 읽기 전용 마운트/탐색만 허용; 그 안의 PKG/APP를 다시 식별. 이미지 종류별 지원 여부 구분.
- **`.app`**: 배포되는 일반 앱인지 자체 GUI 설치 도우미인지 탐지. Intel-only 설치 도우미는 실행 엔진 없이는 지원되지 않을 수 있음.

### 2.2 초기 **읽기 전용** 구현

ARM64 macOS 호스트에서 제공된 `pkgutil`과 시스템 도구를 사용한다. 입력 경로는 코드에서 인수 배열로 전달하고 shell interpolation을 사용하지 않는다.

```sh
pkgutil --check-signature /path/to/sample.pkg
pkgutil --payload-files /path/to/sample.pkg
pkgutil --expand-full /path/to/sample.pkg /path/to/empty-staging-directory
```

`--expand-full` 지원 여부는 대상 macOS에서 확인한다. 압축 해제만으로 시스템에 설치된 것은 아니다. 별도로 `Distribution`의 조건부 선택/OS 버전 검사, `PackageInfo`의 install location, BOM과 payload의 실제 경로, 파일 권한, 링크, 실행 비트, Mach-O 아키텍처를 읽어야 한다. 시스템 기본 설치 명령 `installer`는 직접적인 분석 모드의 대체재가 아니며, 신뢰/권한/스크립트 조건을 충족한 경우의 별도 선택 경로로 유지한다.

분석 결과의 필드 제안: `package_id`, `source_hash`, `signature_status`, `payload_count`, `install_locations`, `distribution_choices`, `scripts[]`, `embedded_binaries[]`, `external_writes[]`, `warnings[]`, `confidence`. 사용자 파일과 정품 인증 정보를 보고서에 포함하지 않는다.

### 2.3 설치 스크립트와 Intel helper

스크립트 텍스트가 존재한다는 이유로 실행하지 않는다. 셸 스크립트는 시스템 기본 ARM64 셸에서 실행 가능할 수 있지만, 내부에서 Intel 전용 helper, 외부 다운로드, 서비스 등록, 승인되지 않은 시스템 수정 등을 요청하면 차단/경고해야 한다.

정책:
1. 최초 단계에서는 **스크립트 정적 분석만** 지원한다. `preinstall`, `postinstall`, `Distribution`의 요구 조건을 실행/우회하지 않는다.
2. 서명이 있다고 해서 안전이 보장되지 않는다. 코드 서명은 출처/무결성 신호이며 앱 실행 및 보안성 판정과 별개다.
3. `/Applications`, `~/Library`, `/Library` 등 대상으로의 실제 설치는 별도 권한·충돌·원본 파일 소유권 검증 후 명시적 동의 하에만 진행한다. `/System` 변경, SIP/AMFI 비활성화, 커널 확장/드라이버 설치는 금지한다.
4. 원래 설치 스크립트가 필요한 패키지를 단순 파일 추출만으로 **정상 설치**로 표시하지 않는다. 패키지 영수증 DB를 임의로 위조하지 않는다.
5. Intel helper 실행이 필수라면 **MacBridge 관련 기능이 검증되기 전까지 BLOCKED_UNSUPPORTED**로 표시한다. 설치 화면 자체를 재구현한다는 약속은 하지 않는다.

### 2.4 파일 경로·안전·복구

- 패키지는 개별 임시 staging에서 처리하고 파일 쓰기는 가능한 범위 내에서 완전한 작업 계획이 확정된 뒤 수행한다.
- `../`, 절대 경로, 심볼릭/하드링크를 이용한 탈출, 권한 변화, 충돌하는 install-location을 탐지하고 원칙적으로 거부한다.
- 도구는 정품 앱 바이너리 및 서명을 수정하지 않는다. 기존 `/Applications/HwpMac2014.app`의 수정·재서명을 금지한다.
- 설치 원장(install manifest)에는 AltInstaller가 **실제로 쓴** 파일만 기록하며 원본 앱 데이터·공유 파일은 무단 제거하지 않는다.
- 시스템 설치에서 원자적 롤백을 보장하지 않는다. 사용자에겐 어떤 변경이 복구 가능/불가능한지 표시한다.
- 패키지의 DRM, 라이선스 활성화는 변경·우회하지 않는다.

## 3. Windows EXE/MSI: 원본 마법사를 실행

Windows `.exe` 설치 프로그램을 별도의 macOS 마법사로 '번역'하지 않는다. 지원되는 **ARM64-host Wine + x86/x64 변환 런타임**을 확보한 다음 실제 Windows 설치 GUI를 실행한다. 런타임 확보·기본 실행 검증 이전에 성공을 주장하지 않는다. 단순 `wine` 명령이 있는 것과 Apple Silicon의 Intel `.exe` 실행이 가능한 것은 다르다.

### 3.1 WinContainer / Wine prefix

앱별 전용 prefix를 기본으로 한다(예: `~/Library/Application Support/AltRosetta/Containers/Windows/<app-id>/`). 필요하면 공급자별 공유 prefix를 명시적으로 허용한다.

```text
<app-id>/
  drive_c/
    Program Files/
    Program Files (x86)/
    windows/
    users/
  dosdevices/
  system.reg
  user.reg
  userdef.reg
  altrosetta-manifest.json (AltInstaller 관리 데이터; Wine 파일 아님)
```

Windows가 보는 `C:\Program Files\Vendor\Product`는 host의 `<prefix>/drive_c/Program Files/Vendor/Product`와 대응한다. `C:`는 실제 디스크 파티션이 아니다. Wine의 `dosdevices`를 이용해 드라이브 글자를 연결한다. Wine 기본 설정에서 광범위한 호스트 폴더/루트가 노출될 수 있으므로 드라이브 매핑을 **사전 점검**하고 과도한 매핑을 제한한다. **Wine prefix 자체는 보안 샌드박스가 아니다.**

### 3.2 기본 실행 절차 (검증 전 예시)

```sh
export WINEPREFIX="/path/to/WinContainer"
wineboot -i
wine /path/to/setup.exe
wine msiexec /i /path/to/setup.msi
```

이 명령은 Wine 런타임이 실제로 해당 ARM64 Mac에서 동작할 때만 유효하다. 호환성 엔진, `WINEARCH`, Windows 버전, x86/x64 지원 및 앱별 의존성은 런타임 검증 프로필에 따라 설정한다.

- `.exe`: PE 아키텍처와 설치 프레임워크(NSIS, Inno Setup, InstallShield 등)를 탐지할 수 있으면 메타데이터에 보존하고, 원본 설치 GUI를 우선 실행.
- `.msi`: Wine의 `msiexec`를 통해 표준 설치 기능과 custom actions 실행을 검증. MSI 파일을 압축 해제하는 것만으로 설치를 대체하지 않음.
- `C:`, 레지스트리, COM/DLL, 시작 메뉴/바탕화면 바로가기, 폰트, VC++/.NET 등은 prefix 및 Wine 호환성 계층으로 처리.
- installer가 요청하는 Windows 서비스/드라이버/보안 기능/재부팅은 모두 지원 여부를 분리해 판단. **Windows 커널 드라이버는 불가**. '관리자 권한' UI를 macOS 관리자 권한으로 자동 매핑하지 않는다.
- 설치 후 실행 대상은 시작 메뉴 엔트리, MSI 정보, 신규 PE 파일 등을 근거로 후보화하고 사용자 승인 후 AppRegistry에 등록.
- 제거는 원래 uninstall 정보/MSI 제거를 우선 실행하고, 필요한 경우 컨테이너를 보존/삭제하는 분리 옵션을 제공. 공유 파일 및 사용자 문서 보호.

### 3.3 앱 간 충돌·보안

기본은 앱별 격리된 prefix, 인터넷 접근/공유 폴더/클립보드/호스트 파일 노출 최소화. 실행 파일이 호스트 파일을 직접 접근할 수 있는지 별도 경계 테스트가 필요하다. EXE 설치 마법사의 임의 코드 실행은 원본 프로그램 수준의 신뢰가 요구된다. 인터넷에서 다운로드한 설치 파일은 별도로 검증하며 DRM 우회 금지.

## 4. 설치 상태 및 호환성 데이터

AppRegistry의 예시 항목:
```json
{
  "schemaVersion": 1,
  "appId": "example.vendor.product",
  "sourceKind": "windows-exe",
  "host": "macos-arm64",
  "installState": "analyzed",
  "launchState": "not-tested",
  "containerId": null,
  "requiredRuntime": "WinBridge",
  "unsupportedActions": [],
  "manifestPath": null
}
```

실제 실행 성공과 설치 성공은 반드시 별도 필드로 기록. 사용자 문서·개인정보·시리얼을 로그에 남기지 않는다. 업데이트 시 prefix/설치 원장 버전 일치성과 rollback 지원 범위를 재평가.

## 5. 구현 순서와 검증 관문

**P0 — 지금 Codex가 진행할 일:**
- 기존 `tools.inspect_app` / `tests` 패턴에 맞춰 `inspect_pkg` **읽기 전용 CLI** 설계 및 자체 fixture 테스트.
- flat PKG의 기본 메타데이터, script inventory, payload file list, Mach-O 아키텍처 식별과 JSON 출력 구현. `installer` 호출이나 실제 설치·스크립트 실행 금지.
- 깨진 아카이브/잘못된 경로/악성 링크, 스크립트 내 외부 helper 참조, 잘못된 서명 등 실패 사례 테스트.
- Apple Silicon에서 실제 패키지 분석은 **사용자가 권리를 보유한 파일로만 로컬 검증**, 생성 보고서 및 실제 설치 파일은 커밋 금지.

**P1 — 런타임과 독립된 Windows prefix 관리 설계:**
- prefix 파일 시스템 모델과 드라이브/레지스트리 매핑, 보존·삭제·복구 manifest 명세 및 단위 테스트.
- 이 단계는 실제 Windows GUI를 실행하지 않는다.

**P2 — 별도 ARM64 Wine/FEX 런타임 검증:**
- 버전/라이선스/재배포 가능성/entitlement/실행 경로 확인 후 hello-world PE → EXE 설치 GUI → MSI → 제거 순으로 검증.
- Windows 원본 한글 설치 파일을 공유/커밋하지 않는다.

**P3 — MacBridge 기능이 검증된 경우에 한해 Intel helper/복잡한 PKG를 확장.**
- 앱이 사용 가능하다는 주장은 설치·실행·입력·저장 검증 후에만 한다.

## 6. 참조 문서

- Apple: [Rosetta translation environment](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment)
- macOS: [pkgutil 매뉴얼](https://keith.github.io/xcode-man-pages/pkgutil.1.html) — `--check-signature`, `--payload-files`, `--expand-full`
- Wine: [WineHQ](https://www.winehq.org/), [Wine 11.0 릴리스](https://list.winehq.org/hyperkitty/list/wine-releases%40list.winehq.org/message/UL6L2GJ55VYUJ5KUMBZ3TZSXRFJ52QG6/)
- 기존 프로젝트 규칙: [AGENTS.md](../AGENTS.md), [ROADMAP.md](ROADMAP.md)

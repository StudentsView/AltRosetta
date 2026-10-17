# ADR-003 — AltRosetta 3대 모듈 + AltCore 구조

- 결정일: 2026-10-13
- 상태: **설계 확정 (구현 미완료)**
- 문서 번호: 기존 ADR-002는 `002-malware-safety.md`이므로 아키텍처는 ADR-003으로 구분한다.
- 관련 문서: [기존 MacBridge](../ARCHITECTURE.md), [AltInstaller](../ALTINSTALLER_DESIGN.md), [다중 OS 전략](../MULTI_OS_STRATEGY.md), [Codex handoff](../CODEX_HANDOFF_2026-10-13.md)
- Notion 상위 기획: https://app.notion.com/p/3f8470a2491c81608a6ccdcd8c790075
- Notion 보안 ADR: https://app.notion.com/p/3f8470a2491c813fa897cc04798476b5

## 결정

**AltRosetta = AltRunner + AltInstaller + AltSecurity + 내부 AltCore.**

세 가지가 사용자에게 보이는 **핵심 기능 영역**이다. AltCore는 네 번째 제품이나 필수 root daemon이 아니라 공유 계약·앱 등록·정책 상태·로그·버전·업데이트/복구를 위한 기반이다. 각각 독립된 앱 번들을 요구하지 않는다. 실제 **신뢰 경계는 더 세분된 독립 프로세스/XPC/VM**으로 구현하며 코드 모듈명과 OS 프로세스 수를 1:1 대응하지 않는다.

초기 배포는 **하나의 `AltRosetta.app`** (SwiftUI 후보). 설치/실행/보안 결과를 통합 UI에서 제공하되 보안 통과 전 설치·실행 경로가 열리지 않도록 설계한다.

```text
AltRosetta.app (unprivileged UI)
  |
  +-- AltInstaller (input inspection, install planning, staging, uninstall)
  |     +-- MacPackageAdapter: .pkg, .mpkg, .dmg, .app
  |     +-- WindowsInstallerAdapter: .exe, .msi (native Windows setup GUI via Wine when runtime verified)
  |     +-- LinuxPackageAdapter: ELF/AppImage/deb/rpm inside Linux VM when verified
  |
  +-- AltRunner (execution + lifecycle)
  |     +-- MacBridge: x86_64 Mach-O + translator + Darwin/Cocoa bridge [original priority]
  |     +-- WinBridge: ARM64 host Wine+FEX candidate or separate isolated-VM profile
  |     +-- LinuxBridge: ARM64 Linux VM + ELF/FEX candidate
  |
  +-- AltSecurity (policy enforcement; never a root-powerful generic scanner)
  |     +-- SourceVerifier / static inspection
  |     +-- ClamAV worker (standalone process) + YARA-X rule worker
  |     +-- PolicyEngine (driver/root/system modifications deny, scan failure blocks)
  |     +-- PermissionBroker / quarantine and execution profiles
  |
  +-- AltCore (cross-cutting, internal only)
        +-- ArtifactStore / AppRegistry
        +-- RuntimeProfiles / capabilities + policy data schema
        +-- Transaction journal / Recovery / CrashSupervisor
        +-- AuditLog / Update coordination
```

**주의:** 데이터 모델은 AltCore에 두되 정책 판단의 소유자는 AltSecurity다. 설치/실행 모듈에 `skipSecurity` 우회 플래그나 내부 root 실행 권한을 주지 않는다. 사용자 승인도 악성 판정이나 금지 드라이버를 우회할 권한은 아니다.

## 모듈별 책임과 금지 행동

| 모듈 | 책임 | 직접 해서는 안 되는 일 |
|---|---|---|
| **AltInstaller** | 인입 형식 식별, 패키지 분석, 설치 계획·사용자 확인·staging, 앱 등록/제거. Windows는 **원본 설치 마법사**를 검증된 Wine prefix에서 실행 | 임의 PKG 스크립트 실행, 임의 `sudo`/root, 스캔 미완료 파일 실행, 드라이버 설치 |
| **AltRunner** | 앱별 런타임 선정, guest 실행, 제한된 파일/네트워크 연결, 프로세스/VM 종료·crash 상태 추적 | 검증되지 않은 entitlement 가정, host kernel extension 로드, macOS host 파일 전역 노출 |
| **AltSecurity** | AV 검사(Cisco ClamAV + YARA-X), 출처·서명, 탐지 범위 검증, 차단 정책, OS 권한 분리 검증·승인 | 탐지 성공을 무해성 보장으로 표시, Windows 프로그램에 macOS root 권한 부여, OS의 Gatekeeper/XProtect 우회 |
| **AltCore** | 불변 해시 ID, 앱/런타임/정책 상태, 로그·트랜잭션·버전 관리, 인터페이스·복구 orchestration | 파일 분석기 내장으로 고권한/저권한 프로세스를 합침, 중앙 만능 root daemon 운영 |

ClamAV와 YARA-X는 **포크하지 않고 버전 고정 후 격리된 스캔 워커로 통합**한다. ClamAV GPLv2와 YARA-X BSD-3-Clause 및 서명 DB/재배포 책임은 별도 배포 리뷰 대상. 초창기는 AV/보안 제품 수준의 탐지 범위나 macOS 28에서의 호환성을 주장하지 않는다.

## 데이터흐름과 보안 게이트

### 처음 설치
1. 사용자가 설치 파일을 지정하면 AltCore의 `ArtifactStore`가 사본/해시/출처를 고정한다.
2. AltInstaller는 **읽기 전용** 형태로 패키지 내부 구조/지원 action을 분석한다. 무신뢰 입력 parser는 sandboxed worker.
3. AltSecurity의 AV 및 정책 게이트가 **해당 해시, 의존 파일, 설치 플랜**을 확인한다. 스캔 실패·제한 초과·부분 검사는 `INCONCLUSIVE`; 악성/드라이버는 `BLOCKED`.
4. 승인 가능한 경우에만 AltInstaller가 선택된 user-level staging에 반영한다. 시스템 경로/권한 상승은 v1에서 차단.
5. AltCore가 설치 산출물/실제 경로/권한/업데이트 출처/rollback 가용성을 기록한다. 설치 성공은 앱 실행 성공과 다르다.

### 앱 실행 및 변경
1. AltRunner가 런타임/실행파일/공유 폴더/네트워크를 선택하고 `LaunchRequest` 생성.
2. AltSecurity가 **실제 실행 대상의 고정 해시와 정확한 RuntimeProfile**에 대해 launch 가능 여부를 검증.
3. 실행시 최소권한 user process/sandbox 또는 검증된 VM 경계 안에 격리(지원되지 않은 경계에서는 실행하지 않음).
4. AltRunner는 변경된 EXE/DLL/플러그인 또는 설치 패키지 업데이트를 발견하면 상태를 무효화하고 재검사 요청.
5. crash/타임아웃/guest panic은 AltCore CrashSupervisor에 사건 단위로 기록하되 scanner 실패가 launch 허용으로 전이되어서는 안 됨.

**분리된 상태:** `scanVerdict: NO_THREAT_FOUND|MALICIOUS|SUSPICIOUS|INCONCLUSIVE`; `policyDecision: ALLOW|BLOCK|REQUIRE_REVIEW`; `installState`와 `launchState`는 서로 별도. `NO_THREAT_FOUND`는 `ALLOW`를 의미하지 않음.

### 공유 계약 예시(설계, 실제 API 아님)

```text
ArtifactRef { sha256, contentSize, sourceKind, snapshotId }
ScanReport { artifactHash, clamavVersion, yaraRulesetVersion, coverage,
             skippedCount, limitExceeded, findings, finishedAt }
InstallPlan { planId, artifactHash, targetPaths, requiredActions, driverRequests }
RuntimeProfile { engine, cpu, sandboxMode, fileGrants, networkGrants, version }
PolicyDecision { artifactHash, action, profileHash, verdict, reasonCodes, expiresAt }
InstallReceipt { manifestHash, actualFiles, appId, state, rollbackCapabilities }
LaunchResult { appId, engine, processOrVmId, state, exitReason, crashDiagnostics }
```

**보안 토큰 규칙:** `PolicyDecision`은 검사된 `artifactHash`, **설치/실행 액션**, 프로필 및 정책 버전에 결합되고, 소모 또는 만료되어 임의 다른 payload/다른 프로필에 재사용 불가해야 한다. AltInstaller와 AltRunner에서 확인하는 **검증 완료된 Install/Launch Broker**가 검사를 우회할 수 없는 OS 권한 경계에 있어야 한다. 단순히 UI에서 검사 결과를 참조하는 것만으로 강제가 구현되지는 않는다. XPC와 App Sandbox의 실효성·호환성은 실험으로 검증할 것.

## 프로세스·권한 구조

- `AltRosetta.app`: UI만, 사용자 세션, no root.
- `FileProbeXPC`, `ClamAVScanWorker`, `YaraXScanWorker`: 가능한 최소 샌드박스, 입력은 고정 사본, 네트워크 기본 없음, timeout/memory/disk limits.
- `UpdateBroker`: 서명/서명 DB만 받는 제한된 네트워크 통로; 임의 외부 URL에서 실행 파일 자동 취득 금지.
- `InstallBroker`: 사용자 범위의 allowlisted 경로 조작. 파일 경로 탈출/TOCTOU 검사와 사전·사후 해시.
- `MacRuntimeHost`: 별도 프로세스, JIT/MAP_JIT entitlement 최소화, 검증된 파일 grant만 사용.
- `WinRuntimeHost`: 격리 VM이 신뢰하지 않는 앱의 기본 목표. native Wine은 OS-level sandbox 검증 이후 trusted opt-in. `WINEPREFIX`/C: 매핑만으로 host 격리하지 않음.
- `LinuxVMHost`: Linux VM별 디스크/공유·네트워크 grant 관리. VM의 guest crash와 host kernel panic 분리.
- **v1에서는 privileged helper/system extension/kext/driver를 배포하지 않는다.** 드라이버를 포함하는 installer가 자동 host kernel을 건드릴 수 없는 구조. OS/hypervisor 취약점을 통한 host panic 위험까지 0으로 보장하는 것은 불가능.

Apple XPC documentation: https://developer.apple.com/documentation/xpc
Apple Sandbox: https://developer.apple.com/documentation/xcode/configuring-the-macos-app-sandbox

## 의존성 방향

```text
AltInstaller -----> AltCore contracts <----- AltRunner
       |                                    |
       +-------> AltSecurity API <---------+
                          |
                   AltCore evidence store
```

AltSecurity는 AltInstaller/AltRunner 구현에 **의존하지 않고**, 정형화된 action 및 profile을 입력받아 판정한다. AltCore는 **순수한 타입/저장 및 생명주기 기반**으로 두어 번역기·패키지 파서·AV 엔진을 직접 링크하지 않는다. security gate는 설치/실행 전에 반드시 강제되는 구현 조건이지 단지 추천 UI가 아니다.

## 개발 우선순위(원래 목표 유지)

1. **P0 — AltCore Contracts + AltInstaller read-only PKG analyzer.** 기존 Issue #8을 우선. 설치 실행 없음. 탐지/정책은 mock adapter로 계약을 고정.
2. **P1 — AltSecurity scan workers + PolicyEngine.** 자체 benign/EICAR fixture, 악성/손상/부분검사/드라이버 테스트. 실패할 때는 차단.
3. **P2 — AltRunner MacBridge 병렬 Phase 0.** 기존 FEXCore Darwin/JIT/ObjC ABI 실험을 꾸준히 진행. 이 단계가 핵심 목표.
4. **P3 — WinContainer/ARM64 Wine 및 Linux VM 격리 스파이크.** 처음에는 자체 fixture, 비신뢰 PE는 격리 없는 native 실행 금지.
5. **P4 — 통합 UI + install/launch broker + 롤백/진단/업데이트 + 배포 감사.**

병렬 트랙은 의존성에 맞게 진행할 수 있으나 **포괄적 지원**을 마케팅하지 않는다. 최종 완료 기준은 실행 성공뿐 아니라 문서/IME/저장, 권한·탐지 누락시 fail-closed, crash/restart 안전성 검증을 포함한다.

## 현재 저장소와의 호환성

기존 `docs/ARCHITECTURE.md`와 `docs/ROADMAP.md`의 MacBridge Phase 0 게이트는 유지한다. 새 모듈은 **명명/책임·인터페이스 결정**으로만 추가한다. 실제 코드는 아직 없다. 변경 후 AGENTS.md의 private/no-DRM/no-SIP 규칙을 우선 적용한다.

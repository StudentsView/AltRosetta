# ADR-002: AltRosetta의 3대 핵심 모듈과 보안 경계

- 작성: 2026-10-13
- 상태: **프로젝트 아키텍처 방향 채택 / 구현·보안 검증 전**
- GitHub: 비공개 AltRosetta 저장소
- 기존 ADR-001 및 Phase 0의 Intel macOS 앱 실행 연구 목표는 유지한다.

## 결정

사용자에게 보이는 제품은 **AltRosetta.app 하나**다. 제품의 핵심 기능 영역은 **AltRunner(실행), AltInstaller(설치), AltSecurity(보안)** 세 가지이며, **AltCore**는 공통 내부 라이브러리/계약과 상태 관리다. 세 가지는 앱 세 개, root 서비스 세 개, 모든 기능을 한 프로세스에서 실행한다는 의미가 아니다. 특별한 권한이 있는 컴포넌트는 앱과 분리하고 최소권한 원칙을 지킨다.

```text
AltRosetta.app (SwiftUI UX + App Library)
    ├── AltInstaller (plan / stage / install / remove)
    ├── AltRunner    (runtime select / launch / watch / stop)
    │     ├── MacBridge   (Mach-O x86_64, Darwin/ObjC/ABI)
    │     ├── WinBridge   (PE, ARM64-host Wine/FEX or validated VM route)
    │     └── LinuxBridge (Linux ARM64 VM, ELF, optional guest FEX)
    ├── AltSecurity  (intake scan / policy / runtime capability enforcement)
    │     ├── ClamAVScanWorker  [candidate, independent process]
    │     ├── YaraXScanWorker   [candidate, independent process]
    │     ├── PackagePolicyEngine
    │     └── Source/Signature/Update Verification
    └── AltCore (shared models + registry + settings + audit + recovery state)
```

**신뢰 경계:** 정적 분석·백신·런타임·설치 계획·실제 쓰기 수행 프로세스를 분리한다. 한 단계 통과가 전체 작업을 자동 승인하는 것은 아니다. 보안 승인/정책 실행에 실패하면 **기본 차단(fail closed)**한다.

## 각 모듈의 책임과 금지

### AltRunner
- 유효한 런타임 선택, 명시적 사용자 실행 승인, 앱 라이프사이클, 종료/크래시/중단 감시 및 실행 로그.
- 자체 보안 정책 우회 또는 앱에 관리자 권한 위임 금지.
- MacBridge/WinBridge/LinuxBridge는 **AltRunner의 하위 백엔드**이며 별도 최상위 제품이 아니다.
- macOS 28에서 Intel macOS 앱 호환성은 **아직 입증되지 않음**. 설치 성공 ≠ 실행 성공.

### AltInstaller
- 형식 판별 및 읽기 전용 분석, 설치 계획, 스테이징, 사용자 검토, 설치/업데이트/제거, 원장 및 복구.
- `.pkg/.mpkg/.dmg`: 패키지 구조 및 스크립트 존재 읽기. 처음부터 설치 스크립트를 실행하지 않는다.
- `.exe/.msi`: 런타임 검증 이후 원본 Windows wizard를 지원 Wine 환경에서 실행. Wine prefix의 `drive_c`는 보안 샌드박스가 아님.
- 드라이버/커널 확장/시스템 보호 비활성화/임의 관리자 권한 코드 실행 불허.

### AltSecurity
- 보안 검사와 실행·설치 정책의 **중앙 결정 주체**. ClamAV + YARA-X는 선택된 통합 후보이며 실제 제품 포함 전 라이선스/ABI/실행 정책·성능·격리 테스트를 통과해야 한다.
- 파일 서명/출처/해시, 정책 위반, 크래시/스캔 누락/검사 상한, 런타임 경계, 컨테이너/VM 접근 허가를 관리한다.
- 애플리케이션 검사기의 'No threat found'는 '안전 확정'이 아니다. ClamAV의 파서 자체도 외부 입력을 처리하므로 독립 비특권 프로세스와 제한이 필요.
- 개별 런타임 프로세스에 실질적인 OS 권한 제한을 적용하고 테스트해야 한다. AltSecurity API에서 '허용'을 반환했다는 이유만으로 접근 통제가 완성되지는 않는다.

### AltCore
- 단순 공통 라이브러리 및 `AppRegistry`, 상태, DTO, 정책 버전, 이벤트, Recovery metadata 등의 저장 기능.
- 절대 God Object로 만들지 않는다. 비밀·원본 상용 설치 파일·인증 정보는 GitHub 또는 진단 로그에 저장하지 않는다.

## 단방향 계약 및 독립 검증

```text
Import(file) -> AltSecurity.inspectAndVerdict(snapshot)
             -> AltInstaller.plan(snapshot, verdict)
             -> AltSecurity.authorizeInstall(plan, capabilities)
             -> AltInstaller.stageAndCommit()

Launch(appId) -> AltSecurity.authorizeLaunch(appId, hash, runtimePolicy)
              -> AltRunner.launch(isolatedRuntime)
              -> AltRunner.watchAndReportCrash()
              -> AltSecurity.revokeOrRestrictOnPolicyViolation()
```

- 서명검사/해시검사 후 파일이 바뀌지 않도록 immutable snapshot/재검증.
- 스캐너 실패·부분 검사·파일 검증 오류: `INCONCLUSIVE` → 새 앱 실행·설치 차단.
- 위험한 드라이버/권한 요청: `POLICY_BLOCKED` → 명시적 차단.
- 정형 install plan만 수락. 승인되지 않은 관리자 작업 및 임의 shell 실행 금지.
- 최종 권한 enforcement는 검증된 App Sandbox/XPC/VM/OS 파일 접근 경계에서 수행. Wine prefix, YARA/AV 검사만으로 격리 보장 불가.

## 실제 프로세스 배치 (목표 설계)

- `AltRosetta.app`: 비특권 GUI 및 승인 UX.
- `FileProbeService`: 최대한 제한된 sandboxed worker.
- `ClamAVScanWorker` / `YaraXScanWorker`: 앱과 분리된 검사 프로세스, 시간/메모리/파일 수·디스크 제한.
- `InstallBroker`: 사용자 영역 내 명시적으로 승인된 경로만 쓰기. 첫 버전 **root helper 없음**.
- `MacRuntimeHost`: 분리된 JIT/ABI/guest 프로세스, entitlement 최소화.
- `WinRuntimeHost`/Linux VM: native Wine 안전 경계 검증 전에는 untrusted Windows 앱의 native 실행을 허용하지 않는다.
- `CrashSupervisor`: worker 종료 탐지, crash loop 방지, registry 상태 갱신; 호스트 kernel panic을 사용자 수준 프로세스가 직접 예외처리할 수 있다고 주장하지 않는다.

## 최우선 보안/개발 결정

1. P0: 기존 Mach-O Inspector와 FEXCore Darwin 조사 계속 + **read-only PKG Inspector** (Issue #8).
2. P1: ClamAV/YARA-X 감지 엔진의 독립 worker / coverage / 비정상 종료 fail-closed 검증. 공용 core interfaces를 좁게 설계.
3. P2: 권한 broker/설치 상태 원장·복구 테스트, WinContainer prefix vs VM 격리 부정 테스트.
4. P3: MacBridge, WinBridge, LinuxBridge를 별도 acceptance gate로 검증. **기능 통합은 뒤에, 보안 경계는 먼저**.
5. 릴리스 전: 관리자 권한, 커널/드라이버/시스템 보호 변경 요구는 모두 차단. ClamAV/YARA-X 사용 시 라이선스/데이터베이스 업데이터/공급망/개인정보 동의 검토.

## 관련 문서

- [AltInstaller 설계](../ALTINSTALLER_DESIGN.md)
- [멀티 OS 전략](../MULTI_OS_STRATEGY.md)
- [Codex 작업 지시서](../CODEX_HANDOFF_2026-10-13.md)
- [Phase 0 실행 엔진 구조](../ARCHITECTURE.md)
- [Codex Issue #8](https://github.com/StudentsView/AltRosetta/issues/8)
- Notion: [통합 구조](https://app.notion.com/p/3f8470a2491c81608a6ccdcd8c790075), [위협 모델](https://app.notion.com/p/3f8470a2491c81a1b42ef0b4543987f6)

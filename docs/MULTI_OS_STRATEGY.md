# AltRosetta 다중 OS 호환 전략 (범위 확장 제안)

- 작성: 2026-10-13
- 상태: **제안**, 현재 구현 상태 아님
- 원칙: 프로젝트의 제1목표는 **Rosetta의 일반 Intel Mac 앱 지원 종료 이후에도 한글 2014 VP for Mac 등 Intel 전용 Mac 사무용 앱을 실행하는 기술 검증**이다. Windows 및 Linux는 통합 UI와 설치 기능을 공유하는 별도 확장으로 관리한다.

## 1. 배경 / 불확실성

Apple의 공개 문서에 따르면 Rosetta는 **macOS 27까지 일반 Intel Mac 앱에 제공**되고, 이후 구형 게임용 제한된 기능만 유지된다. macOS 28에서 제3자 변환기의 필요한 커널 API·entitlement가 실제 가능한지는 **미검증**이다. Apple의 Linux VM 내부 x86 번역 기능은 macOS 27에서 직접 통합된다고 설명되지만, macOS 28에서의 사용 가능성을 단정하지 않는다. MacBridge의 JIT, ABI, Objective-C 연계, 보안 승인 없이는 실행 가능성이 증명되지 않는다.

참조: [Apple Rosetta](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment), [Linux VM Intel binaries](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms).

## 2. 공통 프론트엔드 + 분리된 런타임

```text
AltRosetta.app (SwiftUI; proposed)
    |
    +-- FileTypeDetector (Mach-O, PE, ELF; CPU ISA and installer format)
    +-- AltInstaller (see ALTINSTALLER_DESIGN.md)
    +-- AppRegistry + RuntimeManager + Logs
    |
    +-- MacBridge   : Mach-O x86_64 + CPU backend + Darwin ABI + ObjC/Cocoa bridge
    +-- WinBridge   : Windows PE/EXE/MSI + ARM64-host Wine + x86/x64 backend
    +-- LinuxBridge : ARM64 Linux VM + ELF + optional FEX x86/x64 user-mode
```

'하나의 CPU 변환기만 있으면 모든 OS 앱이 실행된다'는 가정은 금물. macOS Mach-O/Darwin, Windows PE/Win32, Linux ELF/syscalls의 로더·ABI·GUI·파일 시스템 인터페이스가 다르다. 엔진의 코드 재사용 여부는 검증 이후에 결정하며 Linux/Windows frontend를 Darwin 호환 계층이라고 부르지 않는다.

## 3. 엔진별 기술 방향

| 대상 | 가설적 실행 경로 | 초기 판정 | 주된 난제 |
|---|---|---|---|
| Intel macOS .app | FEXCore Darwin 이식 후보 + Mach-O loader + Darwin/ObjC/AppKit bridge | 연구중 / 실행기 없음 | ABI, dyld, Objective-C, VM/JIT 정책 |
| Windows x86/x64 EXE | ARM64 macOS용 Wine 실행환경 + x86 변환 엔진(후보 FEX 계열) | 조사/스파이크 필요 | 런타임 포팅, WoW64, COM/.NET, GUI, entitlement |
| Windows ARM64 PE | 호환 Wine ARM64 runtime 여부 별도 확인 | 검증 안 됨 | Windows ARM64 ABI와 지원 상태 |
| Linux ARM64 ELF | Apple Virtualization.framework의 ARM64 Linux VM | 별도 프로토타입 필요 | GUI·입력·파일공유·VM lifecycle |
| Linux x86/x64 ELF | ARM64 Linux VM + 독립 FEX user-mode (또는 검증된 OS 제공 경로) | 별도 프로토타입 필요 | syscall, libraries, ABI, graphics, distro |

LinuxBridge는 원칙적으로 Linux VM **내부**에서 ELF를 실행한다. ELF 파일을 macOS Darwin 프로세스로 직접 변환하는 일반 기능을 약속하지 않는다. Linux VM에 Apple 제공 번역만 의존하면 장기 독립성 목표와 충돌할 수 있으므로 FEX 기반 대안을 조사한다. VM 내부 OS/패키지 라이선스 및 디스크 사용량도 관리한다.

## 4. 공통 UX / 설치

- `.pkg/.mpkg/.dmg`: 읽기 전용 metadata 검사 후 **Mac 패키지 호환 설치**, Intel helper 사용 여부 표시.
- `.exe/.msi`: 지원되는 WinBridge runtime 확보 후 원본 Windows 설치 마법사를 Wine에서 실행; 앱별 prefix에 `C:` drive 제공.
- `.AppImage/.deb/.rpm/ELF`: LinuxBridge가 지원하는 ARM64 distro/패키지 관리자 내에서 처리. 포맷에 따라 보안·의존성·아키텍처를 구별.
- 탐지 → 분석 → 설치 가능성 → 실제 설치 → 실행 가능성/검증 성공 여부는 별도 상태로 노출한다.

## 5. 개발 순서 / 자원 분리

**A. 기존 핵심 작업은 지속 (최상위 연구 트랙)**
1. 기존 `docs/ROADMAP.md`의 FEXCore Darwin spike.
2. JIT/메모리 맵/entitlement 관문.
3. 최소 Mach-O loader/ABI/Objective-C/Cocoa fixture.
4. 그 뒤에만 한글 2014 실제 실행 검증.

**B. 설치 시스템은 병렬의 저위험 트랙**
1. 읽기 전용 PKG Analyzer와 테스트. **MacBridge 완성 전에도 독립적으로 의미가 있다.**
2. Windows prefix/registry/drive 설계.
3. 검증된 ARM64-host Wine 런타임의 installer spike.
4. LinuxBridge는 ARM64 Linux VM basic boot + 기본 Linux GUI부터 시도.

**C. 합치는 시점**
- 두 트랙 모두 정해진 fixture 및 격리 테스트 통과 뒤 RuntimeManager와 AppRegistry 연동.
- 현 단계에 3개 OS 전반 지원, 'Mac에서 모든 exe가 실행됨' 등의 마케팅 표현 금지.

## 6. 보안 및 라이선스

- 사용자 소유 상용 앱/설치 파일/인증 정보/문서는 repository 및 보고서에 올리지 않는다.
- 설치 프로그램·Wine prefix·Linux VM은 자동으로 안전한 격리 공간이 되지 않는다. 호스트 파일/네트워크 접근 정책을 명시적으로 구현하고 테스트한다.
- Windows 커널 드라이버, macOS kext, SIP/AMFI 우회, 인증 우회는 지원하지 않는다.
- Wine/FEX/Darling 등 upstream을 통합하면 **컴포넌트별 라이선스/저작권 표시 및 배포 의무**를 확인한다. '포크할 수 있다'와 '비공개/오픈소스로 재배포 가능'을 혼동하지 않는다.
- repo는 소유자의 공개 승인 전까지 private으로 유지한다.

## 7. 설계 결정이 필요한 질문

1. 첫 Wine 검증용 무료·재배포 가능한 작은 EXE/MSI fixture는 무엇인가?
2. ARM64 Wine + x86 실행의 공개 경로가 요구하는 특수 entitlement/서명 조건은 무엇인가?
3. Windows 앱별 prefix와 공급자별 공유 prefix를 언제 구분할 것인가?
4. Linux guest 배포판 및 GUI 프로토콜은 무엇을 첫 대상으로 할 것인가?
5. macOS 28 베타/릴리스에서 cross-arch·JIT·VM 지원이 실제 어떻게 동작하는가?

관련 구현 사양: [ALTINSTALLER_DESIGN.md](ALTINSTALLER_DESIGN.md) / [Codex handoff](CODEX_HANDOFF_2026-10-13.md).

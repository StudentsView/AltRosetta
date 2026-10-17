# AltRosetta Phase 0: 조사와 재현 가능한 실험

사용자가 전달한 Phase 0 기획과 이번 작업 지시를 초기 범위로 삼는다.
현재 저장소는 비공개이며 공개 전환은 별도 결정한다.

## 이번 작업의 결과

1. 설치된 HwpMac2014.app을 읽기 전용으로 조사한다. 실행 파일, 아키텍처,
   load commands, 링크 의존성, Objective-C section, 코드 서명을 기록한다.
2. Python 표준 라이브러리로 thin/fat Mach-O 조사 도구를 만든다.
   번들 안의 일반 파일만 읽고 심볼릭 링크 및 번들 밖 파일은 따라가지 않는다.
   보고서는 번들 내부 상대 경로와 허용된 Info.plist 필드만 담는다.
   인증 데이터, 사용자 문서, 실행 파일 자체는 복사하지 않는다.
3. ARM64 C++ probe로 MAP_JIT, 쓰기 보호 전환, 명령 캐시 갱신 및 반환값을
   검증한다. sysctl.proc_translated도 확인한다. 이는 CPU 번역 성공을 의미하지 않는다.
4. 직접 작성한 x86_64 assembly를 Mach-O로 빌드하고 조사 도구로 확인한다.
   Intel 파일은 실행하지 않는다. 아직 loader나 DBT는 구현하지 않는다.
5. FEX/Hadron의 실제 소스와 upstream ref를 조사하여 CPU 엔진 선택을 잠정 상태로 유지한다.

## 구조와 기술

- `tools/macho.py`: 바이트 단위의 헤더/load command parser. 범위를 벗어난
  offset, 잘린 파일, 잘못된 command 크기는 명확한 오류로 종료한다.
- `tools/inspect_app.py`: parser를 사용한 번들 inventory 및 선택적 Apple 도구 조사.
- `experiments/jit_probe.cpp`: 현재 호스트의 JIT 최소 실행 실험.
- `tests/fixtures/return42_x86_64.s`: 자체 작성 Intel 테스트 입력.
- `tests/`: parser 손상 입력 및 재현 가능한 CLI 검증.
- `docs/`: 실제 대상 조사, 출처와 SHA, 기술 결정, 다음 실험.
- `CMakeLists.txt`: ARM64 probe 및 x86_64 fixture 빌드, CTest.

macOS ARM64, Xcode Command Line Tools, Python 3.11 이상, CMake, Ninja를 사용한다.
추가 도구와 upstream은 저장소 내부의 ignored 디렉터리에만 준비한다.
SIP 및 AMFI를 바꾸지 않는다. restricted entitlement를 임의로 붙이지 않는다.

## 검증과 다음 관문

parser의 손상 입력 검증, synthetic thin/fat 파일, 실제 Apple linker fixture를
검증한다. JIT 결과는 호스트 OS와 서명 모드를 함께 기록한다.
실제 앱 의존성을 토대로 Darwin C ABI와 Objective-C/C++ ABI 실험을 설계한다.
FEX 초기화와 x86 명령 실행을 통과하기 전 엔진 채택을 확정하지 않는다.
작은 Cocoa 앱의 callbacks까지 통과하기 전 한글 실행 가능성을 약속하지 않는다.

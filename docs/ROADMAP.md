# 다음 검증 관문

## 완료된 초기 준비

비공개 저장소, 앱 조사 도구, 테스트, ARM64 JIT 실험, 자체 static Intel fixture,
출처/SHA 기반 기술 조사를 확보했다. guest 실행기는 아직 없다.

## 1. FEXCore Darwin spike

upstream의 platform guard 이후 필요한 host 의존성을 목록화한다. allocator,
thread/signal/context, VM mapping, JIT 쓰기 보호를 Darwin hook으로 분리한다.
성공 기준은 native context 초기화 → x86 MOV/ADD/RET 수행 → 기대 register 결과이다.
컴파일만 통과하거나 Windows DLL 실행에 성공한 것은 이 관문의 통과가 아니다.

## 2. 주소 공간 / entitlement

첫 한글 segment의 preferred 주소 `0x100000000`, host 16KB / guest 4KB 동작,
저주소 요구, TSO를 격리된 프로세스에서 검증한다. 기존 매핑 덮어쓰기는 금지한다.
Apple Developer 계정의 cross-architecture capability/profile 발급 가능 여부는
실제 포털 접근과 정상 signing을 통해 확인한다. 현재 entitlement는 발급·적용하지 않았다.
커널 지원 true는 권한 취득을 대신하지 않는다. macOS 28 지원도 미확인이다.

## 3. 최소 loader와 Darwin C ABI

자체 static fixture의 segments와 entrypoint를 CPU 엔진에 연결한다. guest 종료를
명시적으로 제공하고 register/stack/memory 결과를 검증한다. 그 다음 dylib binding,
`LC_MAIN`과 dyld 초기화 계약, libSystem import 하나 및 host→guest 콜백을 검증한다.

## 4. Objective-C / C++ / Cocoa

정수, double, small/large struct, varargs, block, C++ 예외 테스트를 먼저 만든다.
guest ObjC class 등록, method dispatch, IMP callback, constructor/`+load` 순서를
검증한 후 자체 Intel Cocoa 앱에서 NSWindow 표시와 이벤트 콜백을 통과시킨다.
다음 단계는 한글 IME, 파일 대화상자, CoreText이며 한글 실행은 그 이후다.

## 5. 실제 한글 검증

먼저 기존 Rosetta 환경의 실행/빈 문서/한글 입력/저장/PDF 기준선을 확보한다.
사용자 문서가 아닌 자체 만든 테스트 문서를 사용한다. 앱의 기존 OS/API 호환성
문제와 AltRosetta의 번역/ABI 오류를 분리한다. 정품 인증 경로는 그대로 보존한다.

현재 설치본만으로 초기 조사가 가능하다. pkg는 clean 설치나 외부 helper 조사에
필요할 때 사용한다. 이 관문 전체를 4주 안에 완성한다고 가정하지 않는다.

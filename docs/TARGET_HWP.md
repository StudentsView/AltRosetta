# 설치된 한글 바이너리 조사

조사일: 2026-10-13 (Asia/Seoul). 경로: `/Applications/HwpMac2014.app`.
사용자가 한글 2014 VP for Mac으로 지정한 설치본이다. 정확한 SKU/구매 이력은
바이너리 구조만으로 검증하지 않았다. 정품 인증 완료 여부는 사용자 제공 정보다.

## 주 실행 파일

- Bundle ID: `com.hancom.office.hwp.mac.general`
- 버전: `10.30.11`, build `3422`
- `Contents/MacOS/HwpMac2014`: thin x86_64, 57,368,880 bytes
- SHA-256: `045796dfcdb2ebefe1fdc833c95020d4c8da55b68f7be5605f713af889a294a0`
- Mach-O/Info.plist 최소 OS: 10.10, 링크 SDK: 11.3
- `LC_MAIN.entryoff`: 75803; preferred `__TEXT`: `0x100000000`
- `__PAGEZERO`: 4GB; 두 `LC_RPATH` 모두 `@executable_path/../Frameworks`
- dylib load command 30개, undefined symbol 이름 1,195개
- `codesign -dv` 표시: Haansoft Developer ID, hardened runtime, 2023-11-24 타임스탬프,
  stapled notarization ticket. 서명 표시 정보이며 전체 무결성 검증 결과는 아니다.

이 설치본은 출시년도 이후 업데이트된 빌드이므로 최초 2014 설치본과 동일하다고
가정하지 않는다. ICU 3개는 최소 OS 10.14를 기록한다. plist의 10.10만으로 실제
전체 앱 최소 요구 OS를 확정할 수 없다.

## 번들 내부 Mach-O 11개

주 실행 파일, `libHncPtnCore`, `libHncXalCore`, `libHncXalMesg`, `libHncXerCore`,
`libHncXsecCore`, `libicudata`, `libicui18n`, `libicuuc`는 x86_64 전용이다.
`GCDWebServers.framework`와 `HancomProductAuth.framework`는 x86_64 + arm64이다.
총 architecture slice는 x86_64 11개, arm64 2개이다.

번들 안에서 `.kext`, `.dext`, 별도 Helpers/XPCServices/PlugIns 디렉터리는 발견하지
못했다. 설치 프로그램이나 번들 밖 `/Library`에 설치된 구성요소는 조사하지 않았다.

## Bridge 설계를 좌우하는 증거

주 실행 파일은 AppKit, Cocoa, Foundation, CoreFoundation, CoreGraphics, CoreText,
Quartz, QuartzCore, ImageIO, WebKit, Carbon, CoreServices, IOKit, CFNetwork,
libSystem, libobjc, libc++와 내부 Hnc/ICU 라이브러리를 링크한다.
UniformTypeIdentifiers와 일부 프레임워크/라이브러리는 weak import이다.
번들 전체에서 중복 제거한 dylib install name은 32개다.

- `_objc_msgSend`, `_objc_msgSendSuper2`, `_objc_msgSend_stret`,
  `_objc_msgSendSuper2_stret`: x86 구조체 반환 규약까지 필요한 실제 증거.
- `___cxa_throw`, `___cxa_begin_catch`, `__Unwind_Resume` 등: C++ 예외와 unwinding 필요.
- `__Block_copy`, `__Block_object_assign`, `__Block_object_dispose`: 블록 콜백/수명 관리 필요.
- `_NSApplicationMain`, NSWindow/NSView class/metaclass import: native runtime에서
  guest class와 IMP를 등록하고 host→guest 메시지 호출을 처리해야 한다.
- NSOpenPanel/NSSavePanel, WKWebView/WebView: 파일 대화상자와 구형/신형 WebKit 경로 존재.
- CoreText/CGContext import: 글꼴 및 PDF/그리기 함수의 구조체·부동소수점 ABI 필요.

주 바이너리의 import 분류는 Objective-C 194개, 블록 5개, C++ exception/unwind
16개, 기타 980개다. 분류는 이름 접두어에 따른 도구의 집계이며 모든 API 사용을
완전히 표현하지 않는다. dlsym 및 런타임 생성 경로는 정적 undefined symbol에서 빠진다.

`__objc_classlist` 2,768 bytes / 8 = 346 pointer entries,
`__objc_catlist` 56 bytes / 8 = 7 entries,
`__objc_selrefs` 29,120 bytes / 8 = 3,640 entries.
포인터 배열 크기에서 계산한 수치이며 실제 활성 클래스/메서드 수를 뜻하지 않는다.

## 인증 및 pkg

HancomProductAuth는 일반 사용자 공간 framework이며 ARM64 slice도 있다.
`nm -arch x86_64 -u`에서는 112개, ARM64에서는 60개 import 이름이 확인됐다.
ARM64 호스트에서 기본 `nm -u`만 쓰면 Intel 경로의 추가 ObjC 등록 API를 놓칠 수
있으므로 조사 도구는 각 slice의 아키텍처를 명시하고 결과를 따로 기록한다.
이를 native로 로드하면 인증이 자동으로 해결된다는 뜻은 아니다. guest 호출 규약,
앱 identity, 저장 데이터 및 원래 인증 경로를 보존하는 별도 검증이 필요하다.
키/인증 데이터는 읽거나 복사하지 않았다. 앱을 실행·변경·재서명하지 않았다.

현재 조사에는 pkg가 필요 없다. pkg는 설치 scripts, 번들 밖 helper, 재현용 clean
installation을 확인해야 하는 시점에 필요할 수 있다. 제공되더라도 Git에 넣지 않는다.

재현 명령은 README에 있다. 전체 raw metadata는 ignored `reports/local/hwp.json`에
보관하고 이 문서에는 개발 판단에 필요한 구조 정보만 기록한다.

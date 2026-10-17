# 잠정 아키텍처

실행 환경을 하나의 거대한 translator로 구현하기보다 검증 관문을 분리한다.
현재 구현된 모듈은 읽기 전용 inspector와 native probe뿐이다.

```text
Installed app → Inspector → Dependency inventory / compatibility evidence

Future ARM64 host
  → Mach-O loader (guest segments, rebasing, binding, initializers, TLS)
  → CPU backend adapter (candidate: Darwin port of FEXCore)
  → Darwin runtime (syscalls, pthread, signals, memory, loader services)
  → ABI bridge (guest↔host calls, aggregates, floating point, varargs)
  → Objective-C integration (class/selector/IMP metadata, callbacks, blocks)
  → Native AppKit / Foundation / CoreText / CoreGraphics
```

macOS의 native dyld에 x86_64 라이브러리를 `dlopen`해서 실행시키는 방식은
사용하지 않는다. guest 이미지의 메타데이터와 코드는 loader/translator가 관리한다.
native framework 호출은 명시적인 ABI adapter를 통해 수행한다.

## 먼저 고정해야 하는 인터페이스

CPU backend는 guest PC/레지스터/스택과 실행 종료 이유를 전달한다. syscall,
imported function, signal 및 host callback은 각각 구분된 실행 전환으로 취급한다.
엔진의 Linux frontend 또는 Windows/Wine 프론트엔드를 Darwin API 구현으로
오인하지 않는다. FEX API를 감싸는 정확한 C++ 인터페이스는 코어 빌드 spike 이후 정한다.

Loader는 segment와 relocation을 바탕으로 guest 가상 주소를 결정한다. 직접 매핑과
주소 변환 중 어느 방식을 사용할지는 `0x100000000`의 실제 매핑 가능성, 16KB host /
4KB guest page semantics, 코어의 메모리 접근 방식을 확인한 후 결정한다.
`MAP_FIXED`로 기존 host mapping을 덮는 실험을 수행하지 않는다.

Bridge는 guest/host 양방향 호출을 제공해야 한다. x86_64의 `objc_msgSend_stret`,
구조체·부동소수점 반환, block invoke, C++ 예외 unwinding, autorelease/TLS,
ObjC image registration 및 `+load`/C++ constructor 순서를 관문에 포함한다.
guest ObjC 메타데이터를 native runtime에 원형 그대로 넘기는 것은 검증된 설계가 아니다.

## 대안 비교

FEXCore 이식이 첫 후보다. 명령어 지원 범위와 기존 테스트 자산이 장점이며 Darwin
host 이식과 frontend/ABI 분리가 추가 비용이다. Hadron의 Wine 스택을 통째로 쓰는
방향은 Windows PE 실행 문제를 해결하므로 이 프로젝트의 Mac 앱 목표와 맞지 않는다.
작은 자체 DBT는 초기 instruction probe에는 유리하지만 한글에 필요한 SIMD,
TSO, 예외, 스레드까지 확장하는 유지보수 비용이 크다. `alt-rosetta`는 이 경로의
참고용 비교 대상이며 제품용 엔진으로 채택하지 않는다.

마일스톤은 날짜 대신 통과 조건으로 관리한다. 사무용 GUI 호환성은 CPU 코어보다
별개이며, 둘 다 통과해야 대상 앱 실행을 시도할 근거가 생긴다.

# ADR-001: FEX는 1순위 후보이며 아직 확정하지 않는다

상태: Proposed / 2026-10-13.

## 근거

FEX upstream은 Darwin 빌드를 명시적으로 거부한다. Hadron의 macOS 실행 경로는
Windows PE의 ARM64EC/WoW64 DLL + Wine이며 native Darwin FEXCore 통합과 다르다.
따라서 초기 기획의 FEX 선정은 검증 전 가설로 유지한다.

## 결정

다음 독립 spike는 FEXCore만 Darwin static library로 빌드하고 context 초기화,
짧은 x86_64 instruction sequence, 반환 레지스터, 반복 JIT patch를 확인하는 것이다.
Linux ELF frontend, Wine DLL 및 Windows API를 프로젝트 런타임에 포함하지 않는다.
Hadron allocator/JIT/guard/signal 패치는 변경 지점을 찾는 참고 자료로 사용한다.
코드를 가져오는 단계에서 patch별 라이선스와 원본 notice를 보존한다.

## 채택 조건

네이티브 ARM64 프로세스에서 FEX 초기화와 최소 x86 명령을 Rosetta 없이 실행하고,
16KB 페이지/시그널/코드 버퍼 hook을 안전하게 제공할 수 있어야 한다.
Darwin 이식 범위와 필요한 dependency/patch를 별도 문서로 기록한다.
조건 미충족 시 후보를 재평가한다. 단일 JIT 성공을 엔진 채택 근거로 삼지 않는다.

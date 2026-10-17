# Contributing

개발 환경과 재현 명령은 README에 있다. 원본 도구는 Python 표준 라이브러리와
Apple SDK를 사용한다. CPU 엔진 통합 전에는 전역 패키지나 Wine 툴체인을 설치하지 않는다.

새 호환성 주장은 host OS/SDK, native architecture, guest fixture, expected/actual
결과와 source SHA를 함께 기록한다. configure 성공, JIT 성공, x86 번역 성공,
GUI 성공 및 실제 문서 보존을 서로 다른 검증으로 취급한다.

상용 앱은 로컬 경로에서 읽고 metadata만 보고한다. 정품 인증 우회나 앱 재서명은
수행하지 않는다. installer 및 사용자 문서도 commit하지 않는다.

파서 변경은 thin/fat, 잘린 command, offset, symlink 테스트를 실행한다.
실행기 변경은 자체 fixture의 반환 register와 메모리 결과를 확인하며, 파일을
macOS가 직접 실행하게 해서 Rosetta가 동작한 결과를 번역 성공이라고 기록하지 않는다.

third-party 코드를 가져오기 전에 정확한 license/notice를 보존한다. 현재 참고한
upstream은 ignored checkout에만 존재한다. 공개 전환과 distribution은 별도 결정이다.

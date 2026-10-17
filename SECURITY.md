# Security and data boundaries

현재 도구는 Phase 0 metadata inspector이다. Mach-O loader나 adversarial binary를
실행하는 보안 경계로 사용할 수 없다. 알려진 구조의 bounds를 확인하지만 모든
Mach-O command/section/entrypoint의 실행 적합성을 검증하지 않는다.

앱 내부 코드/metadata만 조사하고 심볼릭 링크는 따라가지 않는다. generated report는
기본적으로 로컬에 보관한다. 제품 키, 인증 저장소, 사용자 문서, provisioning profile,
signing credential 및 상용 바이너리는 저장소에 포함하지 않는다.

SIP/AMFI/커널을 수정하지 않는다. 제한된 entitlement를 ad-hoc signature에 붙이지
않는다. 현재 native probe의 개발용 JIT 성공이 notarized 배포의 보안 설정까지
검증한 것을 의미하지 않는다.

문제 제보는 이 비공개 저장소의 issue로 남긴다. 바이너리나 인증 자료 대신
최소한의 재현 입력과 개인정보를 제거한 metadata를 사용한다.

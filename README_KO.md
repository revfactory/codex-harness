<p align="center">
  <img src="codex-harness.png" alt="코딩 도구를 갖춘 Codex Harness 로봇 마스코트" width="800">
</p>

<p align="center">
  <a href=".codex-plugin/plugin.json"><img src="https://img.shields.io/badge/Version-0.1.0-brightgreen.svg" alt="버전 0.1.0"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="Apache 2.0 라이선스"></a>
  <img src="https://img.shields.io/badge/Codex-Plugin-purple.svg" alt="Codex 플러그인">
  <img src="https://img.shields.io/badge/Patterns-6_Architectures-orange.svg" alt="6가지 아키텍처 패턴">
  <img src="https://img.shields.io/badge/Mode-Subagents-green.svg" alt="Codex 서브에이전트">
  <a href="https://github.com/revfactory/codex-harness/stargazers"><img src="https://img.shields.io/github/stars/revfactory/codex-harness?style=social" alt="GitHub 스타"></a>
</p>

# Harness for Codex

[English](README.md) | **한국어** | [日本語](README_JA.md)

Codex에서 프로젝트에 맞는 에이전트와 스킬을 구성하는 하네스입니다. 프로젝트를 분석하고 작업을 나눈 뒤, 부모 에이전트가 독립 작업을 서브에이전트에 병렬로 배정하고 결과 통합과 최종 검증을 담당합니다.

[revfactory/harness](https://github.com/revfactory/harness)의 커밋 [`cceac68`](https://github.com/revfactory/harness/commit/cceac68ea1d0ad198ef4b7b906cd238375836387)을 바탕으로 한 독립적인 Codex 마이그레이션입니다. 원본의 팀 설계 흐름과 6가지 아키텍처 패턴을 Codex의 네이티브 에이전트·스킬 구조로 옮겼습니다. 원본의 Claude Code 성능 측정치는 이 마이그레이션의 성능 근거로 사용하지 않습니다.

## 플러그인으로 설치하기 (권장)

터미널에서 다음 두 명령을 실행하세요. 저장소를 직접 복제하거나 Python 설치 도구를 실행할 필요가 없습니다.

```bash
codex plugin marketplace add https://github.com/revfactory/codex-harness.git
codex plugin add codex-harness@codex-harness
```

하네스를 적용할 **대상 프로젝트에서 새 Codex 세션**을 열고 다음을 입력하세요.

```text
$harness 이 프로젝트에 맞는 하네스를 구성해줘. 독립 작업은 서브에이전트로 병렬 처리해줘.
```

플러그인은 `harness` 스킬과 참조 문서, 보조 스크립트를 제공합니다. 요청하면 프로젝트를 분석하고 필요한 에이전트와 스킬을 생성합니다. 미리 정의된 기본 에이전트 5개와 프로젝트 설정을 설치하려면 아래의 [프로젝트 설치 도구](#다른-프로젝트에-설치하기-선택)를 사용하세요.

위 명령 형식은 Codex CLI **0.153.4**에서 확인했습니다. 마켓플레이스를 추가한 뒤 CLI의 `/plugins`에서 **Codex Harness → Harness for Codex → Install**을 선택해 설치해도 됩니다. 설치 후에는 새 세션을 시작하세요. 데스크톱 앱 설치, 로컬 저장소 설치, 문제 해결은 [빠른 시작](docs/quickstart.md#install-as-a-plugin-recommended)을 참고하세요. [공식 플러그인 가이드](https://learn.chatgpt.com/docs/plugins).

## 현재 저장소에서 시작하기 (개발용)

저장소를 내려받습니다.

```bash
git clone https://github.com/revfactory/codex-harness.git
cd codex-harness
```

이 디렉터리를 신뢰하는 로컬 프로젝트로 열고 **새 Codex 세션**에서 다음을 입력하세요.

```text
$harness 이 프로젝트에 맞는 하네스를 구성해줘. 독립 작업은 서브에이전트로 병렬 처리해줘.
```

이 저장소에는 `harness` 스킬과 기본 에이전트 5개가 들어 있습니다. 실행 중 새로 만든 에이전트가 보이지 않으면 해당 프로젝트에서 새 스레드를 시작하세요.

## 다른 프로젝트에 설치하기 (선택)

Python 3.11 이상이 필요하며 별도 패키지 설치는 필요하지 않습니다. 이 저장소의 루트에서 실행하세요.

```bash
python3 scripts/install.py --target /absolute/path/to/project --dry-run
python3 scripts/install.py --target /absolute/path/to/project
python3 scripts/validate.py --project /absolute/path/to/project
```

설치 도구는 `harness` 스킬과 기본 에이전트를 복사하고, 기존 내용을 보존하면서 지원하는 형식의 프로젝트 설정과 `AGENTS.md` 포인터를 병합합니다. 충돌이 보고되면 해당 내용을 확인하세요. 기본값을 추가해야 하는 `agents = { ... }` 인라인 테이블은 `[agents]` 형식으로 펼쳐야 할 수 있으며, 이 경우 설치 도구는 파일을 쓰기 전에 진단을 반환합니다. 사용자 전역 Codex 설정은 변경하지 않습니다. 설치 후 대상 프로젝트를 신뢰하는 로컬 프로젝트로 열고 새 Codex 세션을 시작하세요.

[Codex 플러그인 매니페스트](.codex-plugin/plugin.json)는 표준 `skills/` 디렉터리에서 스킬을 패키징하며, [저장소 마켓플레이스](.agents/plugins/marketplace.json)를 통해 `codex-harness@codex-harness`로 설치할 수 있습니다. 플러그인 설치 자체는 프로젝트 에이전트 TOML, 프로젝트 설정, `AGENTS.md` 포인터를 생성하지 않습니다. 위의 프로젝트 설치 도구가 해당 파일을 설치합니다.

## 멀티 에이전트 동작 방식

| 역할 | 담당 작업 | 설정된 샌드박스 |
| --- | --- | --- |
| 부모 세션 | 작업 배정, 공통 인터페이스, 결과 통합, 최종 검증 | 현재 세션 설정 |
| `harness_explorer` | 관련 코드 조사, 파일·줄 번호를 포함한 근거 반환 | 읽기 전용 |
| `harness_architect` | 작업 경계·의존성·완료 기준을 응답으로 설계 | 읽기 전용 |
| `harness_worker` | 배정된 파일 범위에서 구현 | 작업 공간 쓰기 |
| `harness_reviewer` | 수정 없이 결함과 회귀 위험 검토 | 읽기 전용 |
| `harness_qa` | 테스트 실행, 배정된 테스트·검증 산출물 작성 | 작업 공간 쓰기 |

각 작업에는 목표, 소유 파일, 의존성, 완료 기준을 명시합니다. 에이전트들이 같은 작업 공간을 공유하므로 공통 파일은 한 에이전트가 맡고, 다른 에이전트의 수정은 보존합니다. 독립 작업은 병렬로 실행하며 선행 결과가 필요한 작업은 기다립니다. 부모는 완료된 에이전트를 정리하거나 재사용하고, 가용 슬롯이 부족하면 남은 작업을 순차 처리합니다.

프로젝트 설정은 네이티브 서브에이전트를 활성화하고 **동시 서브에이전트 스레드 수를 최대 3개**로 요청합니다. 부모 세션이 이를 조율하며 런타임 제한에 따라 실제 가용 수는 줄어들 수 있습니다. 모델과 추론 수준은 부모에게서 상속합니다. 자식 에이전트는 기본적으로 재귀 위임하지 않습니다. QA의 제품 코드 수정 금지는 쓰기 가능한 샌드박스 안의 지시사항 경계입니다. 자세한 프로토콜과 샌드박스 적용 범위는 [멀티 에이전트 설계](docs/multi-agent.md)를 참고하세요.

## 디렉터리 구조

```text
AGENTS.md                         프로젝트 진입점
.codex/config.toml                프로젝트 서브에이전트 설정
.codex/agents/*.toml               기본 네이티브 에이전트 5개
skills/harness/                   하나의 실제 스킬 원본
  SKILL.md                        하네스 구성 워크플로우의 기준 파일
  references/                     설계 패턴, 작업 전달, 예시, QA 가이드
  scripts/create_agent.py         프로젝트 에이전트 생성 도구
  scripts/validate.py             구조·실행 완료 검증
  scripts/run.py                  실행 상태·컨텍스트 갱신·세션 수명
  scripts/communication.py        명시적인 협업 사건 기록
.agents/skills/harness             심볼릭 링크 → ../../skills/harness
.codex-plugin/plugin.json         플러그인 매니페스트; skills = "./skills/"
.agents/plugins/marketplace.json  저장소 플러그인 설치 목록
scripts/install.py                프로젝트 설치 도구
scripts/validate.py               저장소 검증 진입점
tests/                            설치·검증 도구 자동 테스트
docs/                             사용법, 아키텍처, 마이그레이션, 호환성
.harness/runs/<run-id>/            실행 장부·입력 패킷·결과·에이전트 레지스트리
_workspace/communications/         메시지 JSONL 기록과 선택적 내보내기
```

이 저장소의 `.agents/skills/harness`는 프로젝트 탐색을 위해 `skills/harness`를 가리킵니다. 플러그인과 프로젝트가 같은 원본을 사용하므로 스킬 복사본을 중복 관리하지 않습니다. 설치 도구는 이 링크를 통해 원본을 읽고 대상 프로젝트의 `.agents/skills/harness/`에 실제 파일을 복사합니다. 설치된 프로젝트에는 심볼릭 링크가 필요하지 않습니다.

파이프라인, 팬아웃/팬인, 전문가 풀, 생성/검토, 감독자, 계층적 분해의 6가지 패턴을 사용할 수 있습니다. 계층적 분해는 부모가 관리하는 의존성 그래프로 구현하며 재귀적인 에이전트 생성을 요구하지 않습니다.

## 실행 상태와 에이전트 간 소통

아래 셸 예제는 선택적 프로젝트 설치 도구가 만드는 경로를 사용합니다. 플러그인만 설치했다면 `$harness`에 설치된 스킬 디렉터리의 보조 스크립트를 사용하도록 요청하세요.

부모는 실제 프로젝트 계획으로 실행을 초기화하고 네이티브 에이전트 ID를 기록합니다. 각 자식에게 프로젝트 루트, 불변 입력 지문, 결정, 스킬, 소유권, 의존성, 완료 기준을 담은 최신 패킷을 전달합니다. 관련 후속 작업은 같은 에이전트를 재사용하면서 입력을 갱신하고, 독립 리뷰는 런타임이 지원할 때 새 컨텍스트로 수행합니다. 기존 모델 상속과 최대 3개 동시 서브에이전트 설정은 유지합니다.

```bash
python3 .agents/skills/harness/scripts/run.py --project . init \
  --plan-file /absolute/path/to/project-plan.json --run-id project-v1
python3 .agents/skills/harness/scripts/run.py --project . ready --run project-v1
python3 .agents/skills/harness/scripts/run.py --project . status --run project-v1
```

작업자는 영향을 주는 발견을 먼저 알리고, 동료에게 필요한 사실을 구체적으로 질문하며 신속히 답합니다. 선행 입력 준비와 인계도 전달하되 계약과 소유권은 부모가 확정합니다. 중요한 메시지는 `_workspace/communications/<run-id>.jsonl`에 명시적으로 기록합니다. 발신 기록 → 실제 네이티브 전송 → 전송 결과 기록 순서를 따르고 답변은 원래 이벤트 ID에 연결합니다. 읽기 전용 역할은 부모에게 기록·전달을 요청합니다. 로그 도구가 메시지를 보내거나 Codex 내부 대화를 자동 수집하지는 않습니다.

```bash
python3 .agents/skills/harness/scripts/communication.py --project . --run project-v1 view \
  --format markdown --output _workspace/communications/project-v1.md
python3 .agents/skills/harness/scripts/validate.py --project . --run project-v1 --complete
```

작업 결과 완료와 실제 세션 유휴·종료를 구분합니다. 쓰기 소유권을 넘기기 전에는 이전 작성자의 중단·유휴를 확인합니다. 재개 시 입력·결과가 바뀐 작업과 영향을 받는 하위 작업을 다시 실행합니다. 기존 입력 파일 내용만 바뀌면 일반 `resume`을 사용합니다. 결정·소유권·완료 기준·목표가 바뀌거나 작업이 추가·제거되면 이전 실행 장부를 수정하지 않고 새 계획 템플릿을 전달합니다.

```bash
python3 .agents/skills/harness/scripts/run.py --project . resume \
  --run project-v1 --new-run project-v2 \
  --plan-file /absolute/path/to/revised-project-plan.json
```

계약이 바뀐 작업과 영향을 받는 하위 작업은 pending으로 돌리고, 변경 없는 승인 결과는 재사용합니다. 제품 수정은 워커가 맡고 QA는 수정된 동작을 검증합니다. 계획·결과 형식, 명령, 통신 연결 방법은 [실행 가이드](skills/harness/references/runtime-guide.md)에 있습니다.

## 검증

```bash
python3 scripts/validate.py --project .
python3 -m unittest discover -s tests -v
```

실제 네이티브 실행을 확인하려면 인증된 Codex 클라이언트가 있는 환경에서 이 저장소 루트의 다음 명령을 실행하세요. 대상은 새 디렉터리로 지정합니다.

```bash
python3 scripts/live_smoke.py run --target _workspace/live-tests/NEW_ID
```

이 스크립트는 커스텀 워커 2개, 차단된 작업과 완료 검사 실패, 입력 수정 후 재개·변경 없는 결과 재사용, QA 단언 2개를 확인합니다. 제한 시간은 1,200초이며 기본 CI에는 포함되지 않습니다. 실제 대화 기록·파일·검사 결과를 확인해야 하며 명령 안내 자체가 통과 기록은 아닙니다.

**자동 테스트 97개가 통과**했습니다. 여러 번 재개한 작업이 과거 실행의 산출물을 덮어쓰던 문제를 수정했습니다. [검증 요약과 미해결 실행 간 제약 2건](docs/verification/resume-provenance-2026-09-17/README.md)을 별도로 정리했습니다. 별도로 **Codex CLI 0.153.4에서 네이티브 커스텀 워커 2개와 독립 QA 에이전트**를 사용해 파일 작성, 동료 통신 기록, 차단 상태의 완료 거절, 부분 재개, 성공 결과 재사용, 최종 테스트 통과를 확인했습니다. [검증 기록](docs/verification.md)에 근거와 범위, 이전 읽기 전용 실행과 ephemeral 세션에서 관찰한 문제를 남겼습니다. 다른 클라이언트, 샌드박스의 강제 적용, 성능 향상까지 검증한 것은 아닙니다. 사용 환경에서는 위의 실제 실행 검증 명령으로 확인할 수 있습니다.

- [빠른 시작](docs/quickstart.md)
- [멀티 에이전트 아키텍처와 작업 패킷](docs/multi-agent.md)
- [Claude Code → Codex 변경점](docs/migration.md)
- [Codex 호환성](docs/compatibility.md)
- [서비스 마이그레이션 시작 예제](examples/service-migration/README.md)
- [기여 가이드](CONTRIBUTING.md)

## 라이선스와 원본

[Apache License 2.0](LICENSE)을 따릅니다. 원본 Harness는 [revfactory/harness](https://github.com/revfactory/harness) 기여자들의 작업입니다. 원본 라이선스를 유지하며, Codex 마이그레이션의 동작과 검증 상태는 원본 릴리스와 구분하여 기록합니다.

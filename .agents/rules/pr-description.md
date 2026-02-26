---
trigger: model_decision
description: 커밋 후 PR Description 작성 가이드 및 양식 (PR Description Guidelines & Template)
---

# PR Description Rule

PR 리뷰어가 변경 사항을 빠르고 정확하게 파악할 수 있도록, PR을 생성할 때는 다음 규칙과 양식을 따릅니다.

## PR 제목 (Title) 관례

- `태그: 간단한 설명` (예: `feat: 로그인 기능 추가`, `chore: 프로젝트 초기 설정`)
- 태그 목록:
  - `feat`: 새로운 기능 추가
  - `fix`: 버그 수정
  - `docs`: 문서 수정
  - `style`: 코드 포맷팅 (코드 로직 변경 없음)
  - `refactor`: 코드 리팩토링 (기능 변화 없음)
  - `test`: 테스트 코드 추가/수정
  - `chore`: 빌드 업무 수정, 패키지 매니저 설정 등

---

## PR Description 양식 (Template)

PR 본문은 아래 양식을 복사하여 상황에 맞게 작성합니다. 제목 제안이 필요한 경우 모델에게 PR 제목을 제안해달라고 합니다.

```markdown
## PR 목적 (What & Why)

- 이 PR이 왜 필요한지, 어떤 문제를 해결하는지 명확하게 설명합니다.
- (예: 프로젝트 초기 환경 설정을 마무리하고, RAG 파이프라인 및 에이전트 그래프 기본 구조를 잡기 위함)

## 주요 변경 사항 (Key Changes)

- 코드의 주요 수정, 추가 사항을 일목요연하게 나열합니다. 컴포넌트나 레이어별로 설명하면 좋습니다.
- **[Component/Layer Name]**
  - 변경점 1
  - 변경점 2

## 스크린샷 및 실행 결과 (Optional)

- UI 변경, 기능 시연(GIF), 혹은 백엔드 테스트 결과 로그 등을 첨부합니다.

## 관련 문서 및 이슈 (Related Issues)

- 관련된 지라 티켓이나 깃허브 이슈 링크를 추가합니다. (예: `Resolves: #123`)

## 유의 사항 (Notes for Reviewer)

- 리뷰어가 특별히 주의 깊게 봐주었으면 하는 부분이나, 배포 전/후 확인해야 할 의존성 변경 사항 등을 적습니다.
```

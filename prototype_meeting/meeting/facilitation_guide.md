# Expert Meeting Facilitation Guide

## Session purpose

Evaluate whether medical-device-domain experts can:

- understand each prototype without computer-science knowledge
- complete realistic tasks
- identify useful and unnecessary functions
- understand the boundary between observed evidence and model interpretation
- recognize public-data privacy boundaries

Do not use the session to persuade participants that the model is correct.
Observe where the interface or explanation fails.

## Recommended format

- Participants: 4–8 per session
- Duration: 45–60 minutes
- Devices: one projected screen plus optional participant laptops
- Roles: facilitator, note taker, prototype operator
- Language: Korean

## Opening script (3 minutes)

Explain:

1. Every displayed organization and value is generated example data.
2. We are testing the screen and functions, not participants.
3. Participants may think aloud and ask questions.
4. “확인 필요” does not mean illegal or confirmed anomalous.
5. Class 3 intentionally does not reveal named company results.

Do not explain GNN, BC, HHI, or clustering before the first tasks. The first
attempt measures whether the UI explains itself.

## Class 1 tasks (12–15 minutes)

Index meanings and intended calculations (Korean, for participant questions):
[`class1_user_guide.md`](./class1_user_guide.md).

### Task 1: Find and orient

Prompt:

> `C 유통`을 찾아 이 업체에 물품을 공급한 업체 수와 이 업체에서 공급받은 기관 수를 말씀해 주세요.

Observe:

- Can the participant find the search?
- Can they distinguish inbound and outbound?
- Do they understand arrow direction?
- Do they notice the three-month period?

### Task 2: Understand the network

Prompt:

> 선 굵기를 공급 수량 기준으로 바꾸고, 2단계 연결을 열어 달라진 점을 말씀해 주세요.

Observe:

- Does the control label explain the change?
- Is the two-hop view still readable?
- Is node size understood without explanation?

### Task 3: Judge the evidence

Prompt:

> 확인 필요 업체 한 곳을 골라 왜 확인 목록에 있는지, 그리고 무엇을 추가로 확인해야 하는지 말씀해 주세요.

Observe:

- Can the participant separate fact, model interpretation, and question?
- Do they mistake score for probability or wrongdoing?
- Which technical term blocks understanding?

### Statistical-expert follow-up

- Is BC an appropriate label for the hub view?
- Are PDI, HHI, robust price comparison, and time-lag represented accurately?
- What score-calibration evidence is required before operational use?
- Are uncertainty and missing-endpoint caveats sufficient?

## Class 3 tasks (12–15 minutes)

Index meanings and intended calculations (Korean, for participant questions):
[`class3_user_guide.md`](./class3_user_guide.md).

Prefer the **혁신 시안** (`innovation/class3.html`) for the full firm → 품목명 sequel.
Regions are `수도권` / `비수도권` / `전국`.
The **기존안** can run Task 4 via the **품목명 통계** tab if the operator prefers the control UI.

**Operator note (before Task 3):** 리포트 생성 후 **품목군 검토 지도**는 기본으로 열려 있습니다.
진단 아래 「품목군 검토 지도 보기」로 바로 스크롤할 수 있습니다.

### Task 1: Define a profile

Prompt:

> 본인 업무와 가까운 업종, 권역(수도권·비수도권·전국), 품목군을 선택해 해당 기업군을 만들어 주세요.

Observe:

- Which category is difficult to choose?
- Does the participant try to enter a company name?
- Is 품목군 understood as distinct from 품목명?

### Task 2: Read 거시 · 진단

Prompt:

> 거시 요약과 진단(관측·해석·유의점)에서 현재 특징 한 가지와 최근 변화 한 가지를 말씀해 주세요.

Observe:

- Are range bands easier than exact ranks?
- Does the participant confuse change with absolute size?
- Is the diagnosis block clearer than question cards alone?
- Do they notice the privacy one-liner (회사명·순위 비공개)?

### Task 3: Read the product-group map

Prompt:

> 품목군 검토 지도(또는 「품목군 검토 지도 보기」)에서 확인할 품목군 하나를 고르고, 집중도·증감·공급자 규모를 구분해 설명해 주세요.

Observe:

- Can the participant read x=집중도, y=증감률, bubble=공급자 수(소·중·대)?
- Do they treat the map as an investment recommendation?
- Which additional context is needed?

### Task 4: 품목명 statistics sequel

Prompt:

> 「관심 의료기기 알아보기」(혁신) 또는 「품목명 통계」 탭(기존안)에서 추천 검색어로 품목명을 고르고, 집계 통계가 색인(index)이 아닌 이유를 말씀해 주세요.

Observe:

- Do participants confuse 품목군 with 품목명?
- Is the statistics framing clear (especially if they open 취급 맥락 비중)?
- Would they want an index-style lookup elsewhere?

### Optional (if time): Sparse / privacy demo

Prompt:

> 왜 특정 회사의 정확한 값과 순위를 볼 수 없는지 설명해 주세요.

Facilitator demos:

- `기타` + `비수도권` → suppress (공개 제한 화면, 02·03 단계 비활성)
- `기타` + `수도권` → thin history (no trend)

Observe:

- Is the public/private boundary clear?
- What authenticated private features would be valuable later?

## Closing discussion (10 minutes)

Ask in this order:

1. Which screen would you use first in real work?
2. Which term or number was hardest to understand?
3. Which result would change a work question or action?
4. Which function is unnecessary?
5. Which missing function is essential?
6. What information must never be public?
7. Would an authenticated private “내 회사” mode be useful? For what task?

## Metrics to record

For every task:

- completed without help: yes/no
- completion time
- number and type of facilitator hints
- confidence: 1–5
- interpretation error
- terminology confusion
- requested data or function
- privacy concern

## Stop conditions

Stop or correct the session immediately if:

- a participant believes the mock entity is real
- a participant treats the score as legal proof
- sensitive operational data appears unexpectedly
- the local server exposes a source-data directory listing
- the prototype fails and the facilitator cannot restore it quickly

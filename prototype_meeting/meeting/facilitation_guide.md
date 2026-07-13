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

### Task 1: Define a profile

Prompt:

> 본인 업무와 가까운 업태, 권역, 품목군, 규모를 선택해 비교 기업군을 만들어 주세요.

Observe:

- Which category is difficult to choose?
- Does the participant try to enter a company name?
- Is “규모” understandable without exact financial values?

### Task 2: Read position and change

Prompt:

> 비슷한 기업군과 비교해 현재 특징 한 가지와 최근 변화 한 가지를 말씀해 주세요.

Observe:

- Are range bands easier than exact ranks?
- Does the participant confuse change with absolute size?
- Is the comparison cohort definition trusted?

### Task 3: Identify a product question

Prompt:

> 품목 변화 지도에서 확인할 품목 하나를 고르고 그 이유를 설명해 주세요.

Observe:

- Can the participant interpret growth and concentration?
- Does “기회” sound like an investment recommendation?
- Which additional context is needed?

### Task 4: Check privacy

Prompt:

> 왜 특정 회사의 정확한 값과 순위를 볼 수 없는지 설명해 주세요.

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

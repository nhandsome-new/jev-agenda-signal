# Office move meeting (`office_move`)

The team prepares a move to a new office. The move date is settled early, then reopened when a building notice shows the elevators are down that day, and settled again one week later. Seating is debated with no conclusion. The moving company and the IT move are settled together in one sentence. Telling clients about the new address comes up without the word 'notice' and is left for next week.

Korean transcript: 84 utterances, 3,142 characters, last utterance at 19:40.

## Expected signals

| Time | A1 Move date | A2 Moving company | A3 Seating | A4 IT move | A5 Client notice |
|---|---|---|---|---|---|
| 05:00 | 🟢 | 🔴 | 🟡 | 🔴 | 🔴 |
| 10:00 | 🟡 | 🔴 | 🟡 | 🔴 | 🔴 |
| 15:00 | 🟢 | 🟢 | 🟡 | 🟢 | 🔴 |
| 20:00 | 🟢 | 🟢 | 🟡 | 🟢 | 🟡 |
| **Final** | **🟢** | **🟢** | **🟡** | **🟢** | **🟡** |

## Traps

| ID | Agenda | Expected | What happens |
|---|---|---|---|
| `move-reopened-and-resettled` | A1 | 🟢 | The date is settled, reopened after a building notice, then settled again. |
| `move-two-in-one-sentence` | A4 | 🟢 | The IT move is settled in the same sentence as the moving company. |
| `move-indirect-client-notice` | A5 | 🟡 | Clients' address change is raised as 'when should we tell them', with no conclusion. |

## Signal changes

| Time | Agenda | Signal | Why | Utterance |
|---|---|---|---|---|
| 01:42 | A1 | 🟡 | move date raised | 좋네요. 그럼 준비할 게 많으니까 하나씩 봅시다. 먼저 언제 옮길지부터 정하죠. |
| 03:06 | A1 | 🟢 | lead settles Dec 6 | 그럼 12월 6일 토요일로 합시다. 다들 괜찮죠? |
| 03:24 | A3 | 🟡 | seating raised | 다음은 자리를 어떻게 배치할지예요. 새 사무실은 한 층을 다 쓰니까 이번에 좀 바꿔 볼 수 있어요. |
| 09:11 | A1 | 🟡 | date reopened after the elevator notice | 그럼 6일은 안 되겠네요. 날짜는 다시 봐야겠어요. |
| 10:10 | A1 | 🟢 | lead re-settles Dec 13 | 그럼 한 주 미뤄서 12월 13일 토요일로 합시다. |
| 10:31 | A2 | 🟡 | moving company raised | 그다음은 이사 업체요. 서준 씨가 견적 받아 봤죠? |
| 12:22 | A4 | 🟡 | IT move raised | 전산 장비 얘기가 나왔으니까 네트워크랑 PC는 어떻게 옮길지도 같이 봅시다. |
| 14:35 | A2 | 🟢 | lead settles company B | 좋아요. 그럼 업체는 B업체로 하고, 네트워크랑 PC는 IT팀이 금요일 밤에 먼저 옮기는 걸로 둘 다 정합시다. |
| 14:35 | A4 | 🟢 | same sentence settles the IT move | 좋아요. 그럼 업체는 B업체로 하고, 네트워크랑 PC는 IT팀이 금요일 밤에 먼저 옮기는 걸로 둘 다 정합시다. |
| 15:17 | A5 | 🟡 | client notice raised indirectly | 그리고 거래처 쪽에는 주소가 바뀌는 걸 언제쯤 알려 드려야 할까요? 택배나 우편물로 오는 서류도 꽤 있어서요. |

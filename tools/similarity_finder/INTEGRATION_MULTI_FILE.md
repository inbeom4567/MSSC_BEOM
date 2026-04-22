# 복수 파일 입력 + HWP 자동 변환 통합 가이드

## 목적
기존 `main.py`의 단일 HWPX 전용 입력을
- 여러 문제집 파일 동시 선택
- HWP 자동 HWPX 변환
으로 확장한다.

## 구성 모듈
- `converter.py` — HWP→HWPX 변환 (한컴 COM). `hwp_to_hwpx()`, `hwp_to_tempfile()`, `shutdown()`.
- `multi_file_input.py` — 복수 파일 선택 + 변환 오케스트레이션. `select_files_and_prepare()`, `prepare_entries()`, `cleanup()`.

## main.py 수정 지점 (힌트)

### 1) HWP 거부 로직 제거
현재 `main.py` **144~149번 줄** (`_on_search` 내부):
```python
if original_path.lower().endswith(".hwp") or problems_path.lower().endswith(".hwp"):
    messagebox.showerror("HWP 미지원", "...")
    return
```
이 블록을 제거하고, 대신 아래 "파일 준비" 단계에서 HWP를 자동 변환한다.

### 2) `_pick_problems` 교체
현재 `main.py` **125~131번 줄** `_pick_problems()`는 `askopenfilename` (단수).
`multi_file_input.select_files_and_prepare()`를 호출해 **복수 선택 + 변환**을 처리.
복수 파일 상태를 보관하기 위해 `self.problems_path: StringVar` → `self.problems_entries: list[PreparedEntry]` 로 교체하거나,
기존 StringVar에는 "3개 파일 선택됨" 같은 요약만 표시.

### 3) `_run_search` 루프화
현재 문제집 1개만 처리. 아래처럼 큐 순회로 변경:
```python
for entry in self.problems_entries:
    problems_bytes = entry.hwpx_path.read_bytes()
    problems_text = read_hwpx(problems_bytes)
    problems = split_problems(problems_text)
    # ... comparator.compare(...) 호출, 결과 병합
```
**복수 파일 시 순차 처리** (병렬은 추후). 각 파일 완료 시 진행 상태 업데이트.

### 4) 원본 파일도 HWP 허용
`_pick_original` (117~123번 줄)도 `converter.hwp_to_tempfile()` 경유로 교체.
원본은 항상 1개라 `askopenfilename`(단수) 유지 + 확장자가 `.hwp`면 변환만 추가.

### 5) 종료 시 정리
`_on_close` (47~51번 줄)에서:
```python
multi_file_input.cleanup(self.problems_entries)
converter.shutdown()
```
호출해 임시 파일과 한컴 COM 프로세스 정리.

## 순차 처리 정책
- 파일 N개 → 변환 N번 → 검색 N번 순서.
- 변환 실패 파일은 errors에 수집 → 검색 완료 후 사용자에게 리스트로 고지.
- 병렬 변환은 한컴 COM이 단일 인스턴스만 허용하므로 **불가**. 검색(Claude API) 병렬은 향후 과제.

## 체크리스트 (다음 세션)
- [ ] `converter.py`의 COM 인코딩 이슈 실측 (한글 경로 backslash/forward slash)
- [ ] 보안 모듈 등록으로 매크로 경고 팝업 억제 검토
- [ ] `multi_file_input.prepare_entries` 단위 테스트 추가 (converter mock)
- [ ] `main.py` 실제 통합 + 수동 E2E (HWP 2개 + HWPX 1개 섞어서 선택)
- [ ] `_on_close` 호출 경로 정리 (좀비 HWP 프로세스 방지)

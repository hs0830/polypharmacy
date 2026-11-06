# 다제복용 약물 상호작용 점검기

식약처 **DUR 병용금기**(법적 근거) + **DrugBank**(참고용)로, 함께 먹는 약 사이의 위험 조합을 점검합니다.

> 의사·약사의 판단을 대체하지 않습니다. **결과가 없다는 것은 안전하다는 뜻이 아닙니다.**

## 동작 원칙
- 제품 → **성분키(INGR_KEY)** → DUR 성분 쌍을 **정확 일치**로 양방향 조회합니다 (부분 문자열 매칭 없음).
- 성분을 확정하지 못한 약은 "안전"이 아니라 **"확인 불가"** 로 따로 표시하고 검사에서 제외합니다.
- 복합제는 성분 리스트를 유지합니다. DUR 금기 성분을 *포함*하는 복합제는 "확인 필요"로 알립니다.
- DUR 비고(예: "48시간 이내 병용금기")는 항상 함께 보여줍니다 (조건부 금기).
- **위험 점수는 만들지 않습니다.** 근거 있는 항목만 등급(금기 / 확인 필요 / 참고)으로 나눕니다.
- 이전 버전의 GNN 예측과 고령자·임부 탭은 제거했습니다 (근거 데이터·검증이 없었음).

## 빠른 시작
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
`data/processed/` 에 미리 빌드된 데이터가 들어 있어 바로 실행됩니다.

> DrugBank 데이터는 라이선스(비상업 이용 등) 때문에 이 저장소에 포함하지 않았습니다. 없어도 DUR 기반 검사는 모두 동작하며, DrugBank 참고 결과만 표시되지 않습니다. 직접 쓰려면 `data/raw/db_drug_interactions.csv` 를 넣고 `python scripts/build_db.py` 를 실행하세요.

## 데이터를 새로 만들기
### 1) 공공데이터포털 인증키 발급
1. https://www.data.go.kr 회원가입 / 로그인
2. 검색창에 **「식품의약품안전처_의약품 제품 허가정보」** 검색 → 오픈API 상세 페이지
3. **활용신청** (개발계정은 보통 자동 승인) — 신청 사유는 간단히 작성
4. **마이페이지 → 데이터 활용 → Open API → 활용신청 현황** 에서 해당 API 클릭 → **일반 인증키(Encoding / Decoding)** 확인
5. 프로젝트 루트에 `.env` 를 만들고(`.env.example` 참고) 키를 넣습니다.
   Encoding/Decoding 어느 쪽이든 동작합니다. 승인 직후에는 키가 반영되기까지 시간이 걸릴 수 있습니다.

> 개발계정은 일일 호출 한도가 있습니다. 스크립트는 페이지 단위로 `data/raw/cache/` 에 저장하므로,
> 한도가 차거나 끊겨도 다시 실행하면 **이어서** 받습니다.

### 2) 수집
```bash
python scripts/fetch_items.py --probe               # 먼저: 키/응답 필드 확인 (각 API 2건만)
python scripts/fetch_items.py --what items          # 제품 목록 -> data/raw/item_list.csv (영문 성분 ITEM_INGR_NAME 포함)
python scripts/fetch_items.py --what ingredients    # (선택) 한글 성분명 -> data/raw/ingredients.csv (한글 성분 검색용)
```
- End Point 는 활용신청 화면에 보이는 값(현재 `.../DrugPrdtPrmsnInfoService08`)과 같아야 합니다. 기본값이 Service08 입니다.
- `items`: `getDrugPrdtPrmsnInq08` (제품 목록) / `ingredients`: 제품별 주성분(성분 1건당 1행). 오퍼레이션 이름은 08→07 순으로 시도해 응답하는 것을 자동 선택합니다. 직접 지정: `MFDS_OP_ITEMS`, `MFDS_OP_INGREDIENTS`
- 실제 응답 필드는 `--probe` 출력으로 확인하세요. 저장 시 **모든 필드를 그대로** 남깁니다.
- 엔드포인트 버전이 바뀌면 환경변수 `MFDS_BASE_URL` 로 바꿀 수 있습니다.

### 2-1) (선택) 약 정보: 효능·주의사항 (e약은요)
앱의 **💊 약 정보** 탭에서 효능·사용법·주의사항·상호작용·부작용·보관법을 보여주려면 아래를 추가로 합니다.
1. 공공데이터포털에서 **「식품의약품안전처_의약품개요정보(e약은요)」** 를 검색해 **활용신청**합니다. (허가정보 API 와는 별도 신청입니다.)
2. `python scripts/fetch_items.py --what easy` → `data/raw/easy_drug.csv`
3. `python scripts/build_db.py` 를 다시 실행하면 `data/processed/drug_info.csv` 가 만들어집니다.
- 키는 보통 계정에 하나라 위 `.env` 의 키를 그대로 씁니다. e약은요에 다른 키가 나왔다면 `.env` 에 `DATA_GO_KR_SERVICE_KEY_EASY=` 를 추가하세요.
- e약은요는 **일반의약품 중심**(공급 실적이 있는 제품)이라 전문의약품 다수는 정보가 없다고 표시됩니다.
- 제품 기본 정보(제조사, 전문/일반, 분류, 허가일)는 허가정보 API 만으로 항상 표시됩니다.

### 3) 그 밖의 원본 (data/raw/)
- `dur_banned.csv` : DUR 병용금기 목록 (성분명A/B, 제품명A/B, 금기사유, 비고, 고시번호, 고시적용일 컬럼 필요)
- `db_drug_interactions.csv` : DrugBank (Drug 1, Drug 2, Interaction Description)
  - DrugBank 데이터는 **라이선스(비상업 이용 등)** 를 확인한 뒤 사용하세요.

### 4) 빌드
```bash
python scripts/build_db.py
cat data/processed/mapping_report.txt     # 매핑률/미매핑 현황
```
- 제품 목록의 `ITEM_INGR_NAME`(영문 성분, 슬래시 구분)을 1차 성분 출처로 씁니다. 성분 개수(`ITEM_INGR_CNT`)와 안 맞으면 확정하지 않습니다.
- `ingredients.csv`(선택)가 있으면 한글 성분명 사전이 커져 한글 성분 검색과 보조 매핑이 좋아집니다.
- 허가취소 등(`CANCEL_NAME` 이 '정상'이 아닌 제품)과 수출용은 기본 검색에서 숨깁니다.
- `data/manual/ingredient_ko_en.csv` (한글 성분명 → 영문) 에 직접 추가하면 미매핑이 줄어듭니다.
- `data/manual/ingredient_synonyms.csv` : 같은 성분의 다른 표기(from,to). 빌드 때 정규화 규칙에 더해집니다. **의학적 동일성은 약사 확인을 권장**합니다.
- 제품의 DUR 표기와 허가정보 표기가 다르면 두 표기를 모두 보존(`ALT_KEY`)해서, 엔진이 둘 다로 DUR 을 조회하고 성분은 합집합으로 봅니다.
- 처방전 사진 인식: 처방전에 인쇄된 **9자리 제품코드**를 허가정보의 `EDI_CODE` 와 정확히 대조하고, 이름은 보조로 씁니다. 코드와 이름이 모두 맞으면 '코드+이름 일치', 하나만 맞으면 확인이 필요하다고 표시합니다. 자동으로 약을 확정하지 않습니다.
- `unmatched_components.csv` : DrugBank 이름과 안 맞는 성분 (제품 수 많은 순, 동의어 보강용)
- `diagnostics/key_mismatch.csv` : DUR 표기와 API 표기가 다른 성분 쌍 (표기 통일 보강용)
- `diagnostics/unresolved_products.csv` : 성분을 확정하지 못한 제품과 그 사유

## 한글 폰트 (PDF)
PDF 는 한글 **TrueType** 폰트를 임베딩합니다. Windows(맑은 고딕)·macOS(AppleGothic)는 자동 탐색되고,
Linux 는 `sudo apt install fonts-nanum` 후 실행하세요. 다른 폰트는 `KOREAN_FONT_PATH=/경로/폰트.ttf` 로 지정합니다.
(Noto Sans CJK 같은 CFF 기반 OTF/TTC 는 사용할 수 없습니다.) 폰트가 없으면 뷰어의 아시아 폰트에 의존하는 내장 폰트로
대체되며, 이때 일부 뷰어에서 한글이 안 보일 수 있습니다.

## 문제 신고와 데이터 검증
- 사이드바의 **문제 신고 · 의견 보내기**로 받은 신고는 이 프로그램이 실행되는 PC(서버)의 `data/feedback/reports.jsonl` 에만 저장됩니다. 외부로 전송하지 않습니다.
- 선택한 약 목록과 오류 내용은 사용자가 체크했을 때만 함께 저장합니다(건강정보 보호).
- 예상치 못한 오류가 나면 화면이 깨지는 대신 안내 문구와 신고 양식이 나옵니다.
- `python scripts/show_feedback.py` 로 접수된 신고를 보고, `--csv 파일.csv` 로 내보냅니다.
- 이메일로도 받으려면 실행 전에 환경변수 `FEEDBACK_EMAIL=주소` 를 설정하세요(신고 후 '이메일로도 보내기' 링크가 나옵니다).
- **데이터를 새로 빌드한 뒤에는** 아래 두 가지를 실행하세요.
  - `python -m pytest -q` : 알려진 병용금기 12쌍(`tests/golden_ingredient_pairs.csv`)이 계속 잡히는지 확인
  - `python scripts/verify_data.py` : DUR 원본 행 표본이 앱에서 실제로 검출되는지 확인 (실패 목록은 `data/processed/diagnostics/verify_missed.csv`)
- 화면 사이드바에는 데이터 기준일(DUR 고시 최신 적용일)이 표시되고 PDF 에도 들어갑니다.
- 사이드바 **보기 설정**에서 '쉬운 설명'과 '글자 크게'를 켤 수 있습니다. '쉬운 설명'은 문구만 바꾸는 게 아니라 화면 구성이 달라집니다: 표·통계·관계도·탭과 영문 성분명을 숨기고, 약 이름 옆에 허가정보의 약 분류를 보여 주며, 해야 할 일과 **약사에게 그대로 보여 줄 질문**만 크게 보여 줍니다.

## 발표/시연 팁
- 사이드바의 **시연용 → 예시 불러오기**로 미리 만든 조합(금기, 성분 중복, 복합제, 확인 불가)을 한 번에 불러옵니다. 예시는 `src/demos.py` 에서 바꿉니다.
- 우측 상단 Deploy 버튼은 `.streamlit/config.toml` 의 `toolbarMode = "minimal"` 로 숨겨져 있습니다.
- 브라우저에서 `F11`(전체 화면), `Ctrl` + `+`(확대)로 글자를 키우세요. 인터넷이 없어도 동작하며 글꼴만 시스템 글꼴로 바뀝니다.
- 발표 전에 처방전 사진 인식(실험 기능)은 꺼 두고, 실제 환자 정보는 화면에 띄우지 마세요.

## 화면 디자인
- 색상·글꼴은 `.streamlit/config.toml`(기본 테마)과 `src/theme.py`(전역 CSS와 카드 컴포넌트)에서 바꿉니다.
- 화면에 들어가는 외부 자료(DUR 사유, 제품명 등)는 모두 HTML 이스케이프를 거칩니다(`tests/test_theme.py`).
- 휴대폰 화면(폭 720px 이하)에서는 카드가 세로로 쌓이고, 긴 성분명은 줄바꿈되며, 통계 카드는 2열로 바뀝니다.
- 글꼴은 Pretendard(인터넷 연결 시)이고, 없으면 맑은 고딕 등 시스템 글꼴로 대체됩니다.

## 테스트
```bash
pip install -r requirements-dev.txt
pytest -q
```

## 구조
```
app.py                     Streamlit 화면
scripts/fetch_items.py     API 수집 (키는 .env, 캐시/재시도/이어받기)
scripts/build_db.py        원본 -> data/processed
src/normalize.py           성분/제품명 정규화 (빌드·런타임 공용)
src/store.py               정제 데이터 로드, 검색, 인덱스
src/engine.py              분석 (DUR 정확 일치 / 복합제 포함 / 성분 중복 / DrugBank)
src/report.py              PDF (한글 폰트 자동 탐색, KOREAN_FONT_PATH 로 지정 가능)
src/ocr.py                 처방전 OCR 후보 제안 (선택, requirements-ocr.txt)
tests/                     단위/통합 테스트
```

## 한계 (꼭 읽어 주세요)
- DUR 목록에 없는 조합은 이 도구가 알 수 없습니다. 연령·임부·용량 관련 DUR 은 포함하지 않습니다.
- 제품 목록의 상당수는 성분 매핑이 안 되어 "확인 불가"로 나옵니다 (`mapping_report.txt` 참고).
- "이름 기반 추정" 표시가 붙은 제품은 제품명 괄호의 성분으로 추정한 것이므로 확인이 필요합니다.
- DrugBank 는 심각도 정보가 없고 영어 원문입니다. 참고용입니다.

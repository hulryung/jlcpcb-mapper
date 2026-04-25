# jlcpcb-mapper

> [English README](./README.md)

KiCad 스키매틱의 **풋프린트 안 정해진 심볼을 JLCPCB 부품(LCSC)에
자동으로 매핑**해주는 CLI입니다. 로컬 `parts.db`에서 후보를 뽑아
점수로 랭크하고, 애매한 건 Claude Code에게 tiebreak를 시킨 다음,
스키매틱에 LCSC + KiCad 풋프린트를 다시 써넣습니다.

저항/세라믹 캡 같은 commodity passive는 거의 자동으로 잡고, 사람이
검토할 수 있게 **각 부품을 왜 골랐는지(점수, LLM 코멘트, 대안 후보
표)** 마크다운 리포트로 뽑아줍니다 — git diff 보기 전에 이 리포트
한 번 훑으면 전체 매핑 결과를 빠르게 검토할 수 있습니다.

## 동작 방식

심볼을 그룹(같은 카테고리 + 같은 spec + 같은 package hint) 단위로 묶어
처리합니다:

1. **Match** — `lib_id`로 카테고리 라우팅 (Device:R → resistor,
   Device:CP → polarized_capacitor, 그 외 `:` 가진 lib_id → ic).
2. **Parse** — Value 필드를 구조화된 spec으로 변환
   (`"4.7uH/2A"` → 인덕턴스 + 최소 전류).
3. **Query** — `parts.db`에서 카테고리/패키지/description LIKE로 후보 추출.
4. **Decide** — 세 갈래:
   - **single** — 필터 후 후보 1개. 그대로 채택.
   - **score** — Basic-tier 가산점 × stock 버킷 × 카테고리별 dimension.
     1위와 2위 점수차가 임계값 이상이면 score path로 결정.
   - **llm** — 박빙이면 상위 N개 후보를 Claude Code에 보내 이유와 함께
     하나 고르게 함.
5. **Resolve footprint** — 일반 SMD passive는 KiCad 내장 매핑, 그 외엔
   EasyEDA에서 즉석 다운로드 (kicad-jlcpcb-tools 헬퍼 사용).

수동 override는 위 파이프라인을 우회합니다 — [수동 LCSC 지정](#수동-lcsc-지정)
참고.

## 사전 조건

- KiCad 9 프로젝트 (`*.kicad_pro`, `*.kicad_sch`).
- JLCPCB 부품 SQLite 카탈로그. `jlcpcb-mapper fetch-db` 한 번 실행하면
  자동으로 받습니다 ([빠른 시작](#빠른-시작) 참고). 이미
  [`kicad-jlcpcb-tools`](https://github.com/bouni/kicad-jlcpcb-tools)
  플러그인을 쓰고 있어 그 DB가 있다면 자동 감지됩니다 — 따로 다운로드할
  필요 없음.
- [Claude Code CLI](https://docs.claude.com/en/docs/claude-code) (`claude`)가
  `PATH`에 있어야 함. tiebreak에 사용하며, 없어도 score path만으로 동작은
  하지만 정확도가 떨어집니다.
- Python 3.12+, `uv` 또는 `pipx`.

## 설치

```bash
pipx install jlcpcb-mapper
# 개발용:
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

## 빠른 시작

```bash
jlcpcb-mapper fetch-db                      # 최초 1회: parts.db 다운로드 (~1GB → 슬림 DB)
cd /path/to/my-kicad-project
jlcpcb-mapper init                          # jlcpcb-mapper.yaml 생성
jlcpcb-mapper map my-project.kicad_pro      # LCSC + 풋프린트 기록
# 리포트 확인:
open .jlcpcb-mapper/run-<latest>.md
git diff                                    # 스키매틱 변경 검토
```

`fetch-db`는 기본적으로 `~/.cache/jlcpcb-mapper/parts.db`에 저장하고
이후 `map`/`verify`가 자동으로 그 위치를 잡습니다.

git tree가 dirty하면 실행을 거부합니다 (`--force`로 우회). 매핑이
마음에 안 들면 언제든 `git checkout .`로 원복할 수 있게 한 안전장치입니다.

## 전체 작업 흐름

KiCad 보드를 처음 매핑할 때 일반적인 순서:

### 1. `parts.db` 준비

```bash
jlcpcb-mapper fetch-db
```

JLCPCB 부품 데이터를 받아 슬림 SQLite 카탈로그를
`~/Library/Caches/jlcpcb-mapper/parts.db` (macOS) /
`~/.cache/jlcpcb-mapper/parts.db` (Linux)에 만듭니다. zip 청크 ~1GB를 한 번
받아 ~100MB DB로 변환. 재고/가격 갱신 위해 주기적으로 다시 돌리면 됩니다.

이미 KiCad에 `kicad-jlcpcb-tools` 플러그인이 있고 거기서 parts data를
받아둔 상태라면 그 DB를 자동 감지하니 다시 받을 필요 없습니다. config의
`parts_db:`로 위치를 명시적으로 지정도 가능.

### 2. 설정 파일 생성

```bash
jlcpcb-mapper init
```

`*.kicad_pro` 옆에 `jlcpcb-mapper.yaml`이 생깁니다. 취미 보드 기준으로는
기본값이 합리적입니다 (passive 0402, X7R/X5R 캡, min_stock 1000).
[설정](#설정) 섹션에서 튜닝 가능.

### 3. 매핑 실행

```bash
jlcpcb-mapper map my-project.kicad_pro
```

내부 동작:

- 스키매틱 파일 로드.
- 심볼 필터링: on-board, Value 있음, `power:*` 아님, **풋프린트 비어있고
  LCSC도 비어있는** 심볼만.
- 카테고리 별로 라우팅 + 그룹화.
- 각 그룹: query → score → (필요시) LLM tiebreak.
- 수정될 모든 `.kicad_sch`의 타임스탬프 백업이 `.jlcpcb-mapper/backups/<ts>/`에
  저장됨.
- LCSC와 Footprint가 atomic하게 다시 쓰여짐.
- 마크다운 리포트(`.jlcpcb-mapper/run-<ts>.md`)와 JSON 로그(`run-<ts>.json`)
  생성.

### 4. 리포트 검토

`.jlcpcb-mapper/run-<latest>.md`를 열어보세요. 각 그룹은 이런 식으로
표시됩니다:

```markdown
### resistor 4700Ω 0402 — 20 refs (R20, R21, R22, R23, R24, R50, … +14 more)

**Selected**: [`C25744`](https://www.lcsc.com/product-detail/C25744.html) — UNI-ROYAL 0402WGF4701TCE
- **Package** `0402` · **Tier** Basic · **Stock** 4.4M · **Price** $0.0009
- 4.7kΩ 1% 1/16W 0402 Chip Resistor

**Why this part?** Score 1.00 vs runner-up 0.40 — Basic-tier (vs Extended), higher stock (4.4M vs 60k).

**Alternatives considered**: …
```

"Why this part?" 라인이 결정 경로를 알려줍니다:
- **single** — 필터링 후 후보 1개.
- **score** — 어떤 차원이 결정적이었는지 (Basic-tier, 재고, 전압 정확 일치 등).
- **llm** — Claude의 한 줄 reasoning 그대로.
- **manual** — config로 못 박아둔 부품 (점수 매기지 않음).

### 5. 승인 또는 원복

```bash
git diff                # 변경사항 확인
git checkout .          # 마음에 안 들면 원복
```

좋으면 스키매틱 변경 + config를 같이 commit.

### 6. 제조 전 재확인

```bash
jlcpcb-mapper verify my-project.kicad_pro
```

현재 `parts.db`로 매핑 다시 조회해서 매핑된 LCSC 중 재고가
`verify.min_stock_warning` 아래로 떨어졌거나 가격이
`verify.price_change_pct_warning`% 이상 변동된 것에 경고.

## 설정

`jlcpcb-mapper.yaml`은 `*.kicad_pro` 옆에 두고, 패키지에 포함된
`default_config.yaml`을 베이스로 deep-merge됩니다.

### Selection 규칙

```yaml
selection:
  prefer_order: [basic, preferred, extended]
  min_stock: 1000
  defaults:
    resistor:
      package: "0402"
      tolerance: "1%"
      power: "1/16W"
    capacitor:
      package: "0402"
      voltage_min: 10
      dielectric_prefer: [X7R, X5R]
    led:
      package: "0603"
```

`prefer_order`는 점수 가중치에만 영향. `min_stock`은 SQL 단계에서 hard
filter — 이 아래는 score path까지 가지도 않고 잘립니다.

### LLM hints

```yaml
hints: |
  - Prefer Basic parts with high stock.
  - Avoid parts with stock < 10000 (EOL risk).
```

LLM 프롬프트 끝에 그대로 붙는 자유 텍스트. 프로젝트 특화 룰
("Y5V 유전체 피하기", "차량용 섹션은 AEC-Q200 우선" 등) 넣기 좋음.

### Tiebreak 임계값

```yaml
score_tiebreak_threshold: 0.1   # 1위-2위 점수차가 이 이상이면 score 채택
llm_tiebreak_top_n: 5           # 그렇지 않으면 상위 N개를 LLM에 보냄
```

### 수동 LCSC 지정

```yaml
manual_lcsc:
  by_reference:
    J2: C16214      # 2.0mm DC 배럴잭 (DC-005 2.0)
    J3: C165948     # USB-C 16P SMD (TYPE-C-31-M-12)
    J1: C492421     # 2.54mm 2x4 핀헤더 (PZ254V-12-8P)
  by_value:
    "POGO (1PI)": C5221287   # 12개 포고핀 심볼 한 번에
    "SW_SPST":    C7470157   # 6×6 택타일 스위치
```

`by_reference`(정확한 ref 지정)가 `by_value`(같은 Value 가진 심볼들 한 번에)
보다 우선. 점수 매기지 않고 그냥 LCSC를 씁니다. `parts.db`에 없는 LCSC를
지정하면 `manual_unknown_lcsc` failure로 표시되고 자동 파이프라인이 그 ref를
계속 처리. **기존 풋프린트는 보존** — manual 모드는 LCSC만 씁니다.

USB-C 리셉터클이나 배럴잭처럼 같은 spec에도 종류가 너무 많아 자동 선정이
어려운 경우, POGO 핀처럼 프로젝트 specific한 부품, 그리고 6×6 택타일 스위치처럼
형상이 중요한 부품들에 적합합니다.

### 풋프린트 오버라이드

```yaml
kicad_footprint_map_overrides:
  resistor:
    "0402": "MyLib:R_0402_HouseStyle"
```

(카테고리, 패키지) → 풋프린트 식별자. 사내 라이브러리가 KiCad 기본 풋프린트보다
엄격한 pad geometry를 쓰는 경우.

## 출력물

`map` 실행마다 `.jlcpcb-mapper/` 아래에 생기는 것들:

| 파일 | 용도 |
|---|---|
| `run-<ts>.json` | 머신 가독 summary — 스키매틱, 적격 카운트, source별 카운트(`single`, `score`, `llm`, `manual`, `failed`), 그룹 결과, 실패 리스트. |
| `run-<ts>.md` | 사람용 리뷰 문서 — 위 예시처럼 LCSC 링크 + 스펙 + 선정 이유 + 대안 표. |
| `traces/<ts>/groups.jsonl` | 그룹당 한 줄, 단계별 전체 트레이스 (match → parse → extract → query → post_filter → score breakdown → decide → resolve). 순서 안정적, `timestamp_ms` monotonic. |
| `traces/<ts>/index.json` | `ref → line offset` 매핑. |
| `backups/<ts>/` | atomic write 직전 모든 `.kicad_sch` 사본. |

## 플래그

**`map`**: `--config PATH`, `--non-interactive`, `--force`,
`--allow-stale-db`, `--fill-lcsc-only`, `--include-dnp`,
`--apply-2nd-pass-suggestions`

**`verify`**: `--config PATH`, `--non-interactive`, `--force`,
`--allow-stale-db`

`--fill-lcsc-only`은 풋프린트 유무 상관없이 "LCSC 비어있는 심볼"을 모두
대상으로. KiCad 심볼 라이브러리에서 풋프린트는 이미 받았고 LCSC만 채우면
BOM 완성되는 경우 유용.

## 지원 카테고리

`resistor`, `ceramic_capacitor`, `polarized_capacitor`, `inductor`,
`ferrite_bead`, `led`, `crystal`, `connector`, `ic` (MPN으로 매칭하는
catch-all). 위에 안 잡히는 것들 — 마운팅 홀, 커스텀 포고 핀, USB-C
리셉터클, 기계식 스위치 등 — 은 `manual_lcsc`로 못 박는 게 가장 깔끔합니다.

## 상태

v0.1 — 실제 KiCad 프로젝트(≈150 eligible 심볼)에 대해 검증 완료, 사람이
직접 픽한 부품과 정확히 일치하는 비율 ~75%. 설계 노트는 `docs/` 참고.

## 향후 작업

- **회로의 논리적 요구를 반영한 부품 선정.** 현재는 심볼의 Value + 풋프린트
  패키지만 보고 부품을 고릅니다. "이 100nF 캡은 3.3V LDO 출력에 붙으니
  16V X7R이면 충분하지만 6.3V Y5V는 안 됨", "이 4.7µH 인덕터는 스위처의
  출력 전류를 견뎌야 하니 부하 전류의 2배 이상 정격이 필요" 같은 회로
  맥락 판단은 사람 검토자 몫. net 토폴로지, 전압 도메인 추론, net별 전류
  추정을 더하면 LLM이 심볼 로컬 정보뿐 아니라 회로 컨텍스트까지 고려해
  tiebreak할 수 있을 것.

## Acknowledgments

`parts.db`의 스키마와 JLCPCB 부품 데이터 피드는
[`kicad-jlcpcb-tools`](https://github.com/bouni/kicad-jlcpcb-tools)와
[`yaqwsx/jlcparts`](https://github.com/yaqwsx/jlcparts)에서 가져옵니다.
이 프로젝트는 같은 데이터를 쓰는 별도 프론트엔드일 뿐, 위 도구들을
대체하지는 않습니다.

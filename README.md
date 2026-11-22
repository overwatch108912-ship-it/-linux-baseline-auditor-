# 🛡️ linux-baseline-auditor

> **KISA 「주요정보통신기반시설 기술적 취약점 분석·평가 방법 상세가이드」의 리눅스(UNIX) 항목을 파이썬으로 옮긴, 읽기 전용 보안 기준선 점검기.**
> 한 줄 명령으로 서버 설정을 점검해 `PASS / FAIL / WARN / SKIP` 판정과 `report.json` · `report.html` 리포트를 만듭니다.

- 상태: **1주차 뼈대 완료** — 점검 항목 **7개 구현 / 20개 목표** (4주 로드맵)
- 의존성: **표준 라이브러리만** 사용 (외부 패키지 0개, Python 3.9+)
- 테스트: **86개 통과** (`python3 -m unittest discover`)
- 실행 환경: Ubuntu/Debian 계열 리눅스 기준으로 작성, macOS·기타 리눅스에서도 실행은 가능(항목별 SKIP 처리)

---

## 1. 한 줄 요약

서버 한 대에 들어가서 손으로 확인하던 "root 원격 로그인 허용?", "/etc/shadow 권한 666?", "world writable 파일이 있나?" 같은 기준선 점검을 **코드로 옮겨 반복 실행 가능한 리포트로 만드는 도구**입니다. 결과는 JSON(자동화용)과 HTML(사람이 읽는 보고서용) 두 가지로 나옵니다.

---

## 2. 4주 로드맵

| 주차 | 목표 | 산출물 | 완료 판정 |
| --- | --- | --- | --- |
| **1주** | 뼈대 + 첫 점검 7개 | CLI, 판정 모델(PASS/FAIL/WARN/SKIP), 계정·파일·SSH 점검 7개, 단위 테스트 86개, JSON/HTML 리포트 | 새 VM에서 `git clone` 후 3줄 실행 → 7개 판정 출력 |
| 2주 | 계정 관리 항목 확장 (총 14개) | U-02·U-03·U-06·U-08·U-10·U-11 추가, PAM 설정 파서 | `--list-checks` 에 14개, 각 항목 테스트 존재 |
| 3주 | 서비스·파일 항목 확장 (총 20개) | U-19·U-28·U-30·U-52·U-54·U-63·U-67 추가, 리스닝 포트 수집(`ss`) | 20개 전체 실행, VM 두 대에서 실행 시간 5초 이내 |
| 4주 | 전후 비교 + 보고서 | 취약 VM → 조치 → 양호 VM 스크린샷 비교표, 오탐 3건 분석, README 정량 성과 | 면접에서 보여줄 수 있는 "취약 → 조치 → 양호" 비교 리포트 |

> 각 주차는 **완성해서 GitHub에 올린 뒤** 다음 주차로 넘어갑니다. 미완성 기능은 README의 "구현 상태"에 ⏳로 남겨 둡니다.

---

## 3. 아키텍처 흐름

```
        ┌──────────────── python3 run.py  (CLI) ────────────────┐
        │  --root /  --scan-path  --only  --json  --html         │
        └───────────────────────┬───────────────────────────────┘
                                │ AuditContext (root, scan_paths, 허용목록)
                                ▼
                   ┌──────────────────────────┐
                   │  engine.run_audit()      │  점검별 예외 → SKIP으로 격리
                   └────────────┬─────────────┘
                                │ 등록소(checks registry)에서 선택
        ┌───────────────────────┼────────────────────────┐
        ▼                       ▼                        ▼
  checks/account.py      checks/filesystem.py     checks/service.py
  U-04 · U-05             U-23 · U-25              U-01
  U-16 · U-18                                   (sshd_config)
        │                       │                        │
        └───────────┬───────────┴────────────────────────┘
                    ▼  CheckOutcome(status, summary, evidence)
            ┌───────────────┐
            │    Report     │  counts · overall 판정
            └───────┬───────┘
         ┌──────────┼───────────────┐
         ▼          ▼               ▼
   콘솔 요약   report.json     report.html
```

설계에서 의도한 세 가지:

1. **읽기 전용** — 점검 코드에는 `open(..., "w")`, `chmod`, `subprocess` 쓰기가 없습니다. 점검이 시스템을 바꾸지 않으므로 운영 서버에도 부담 없이 돌릴 수 있습니다.
2. **`--root` 로 대상을 바꿀 수 있음** — 마운트한 이미지나 임시 디렉터리를 대상으로 점검할 수 있어, 단위 테스트가 실제 `/etc` 를 건드리지 않습니다.
3. **예외는 SKIP 으로** — 권한이 없거나 파일이 없으면 점검이 죽지 않고 "판정 불가"로 남습니다. 확인하지 못한 것을 양호로 세지 않습니다.

---

## 4. 실행 방법 (3줄)

```bash
git clone https://github.com/overwatch108912-ship-it/linux-baseline-auditor.git
cd linux-baseline-auditor
python3 run.py --html report.html
```

`report.json`(기본값)과 `report.html` 이 현재 디렉터리에 생기고, 요약이 콘솔에 출력됩니다.
`pip install -e .` 로 설치하면 `linux-baseline-auditor --html report.html` 로도 실행할 수 있습니다.

### 옵션

| 옵션 | 설명 | 기본값 |
| --- | --- | --- |
| `--root DIR` | 점검 대상 루트 (마운트 이미지·테스트 트리) | `/` |
| `--scan-path DIR` | 파일 탐색 점검(U-23, U-25)의 대상. 여러 번 지정 가능 | `--root` 전체 |
| `--only ID [ID ...]` | 지정한 항목만 점검 | 전체 |
| `--exclude ID [ID ...]` | 지정한 항목 제외 | - |
| `--list-checks` | 구현된 점검 항목 목록 출력 | - |
| `--json PATH` / `--html PATH` | 리포트 경로 | `report.json` / `report.html` |
| `--no-json` / `--no-html` | 해당 리포트 생성 안 함 | - |
| `--max-entries N` | 파일 탐색 최대 항목 수(넘으면 부분 점검) | 200000 |
| `--suid-allowlist FILE` | SUID/SGID 허용 목록 파일(한 줄에 경로 하나, `#` 주석) | 내장 목록 |
| `--no-color` / `--quiet` | 색상 없이 / 요약만 | - |

### 예시 출력

```
🛡️  linux-baseline-auditor v0.1.0
대상: /   호스트: audit-vm   시각: 2026-11-22 09:02:23 KST

[PASS] U-04 비밀번호 파일 보호 (shadow 사용) (상)
       전체 24개 계정이 shadow 로 위임됨
[PASS] U-05 root 이외의 UID가 '0' 금지 (중)
       UID 0 계정은 root 하나뿐
[PASS] U-16 /etc/passwd 파일 소유자 및 권한 설정 (상)
       권한 0644, 소유자 root(0) — 기준 충족
[PASS] U-18 /etc/shadow 파일 소유자 및 권한 설정 (상)
       권한 0400, 소유자 root(0) — 기준 충족
[WARN] U-23 SUID, SGID, Sticky bit 설정 파일 점검 (상)
       허용 목록 밖 SUID/SGID 파일 1건: /usr/local/bin/helper
[FAIL] U-25 world writable 파일 점검 (상)
       sticky bit 없는 world writable 항목 2건: /srv/www/upload, /opt/app/config
[SKIP] U-01 root 계정 원격 접속 제한 (상)
       sshd 설정 파일을 찾지 못해 판정할 수 없음 (sshd 미설치이거나 접근 권한 없음)

────────────────────────────────────────────────────────────
PASS 4 · FAIL 1 · WARN 1 · SKIP 1   →  종합: FAIL (취약)
```

### 종료 코드

| 코드 | 의미 |
| --- | --- |
| `0` | FAIL 없음 (PASS/WARN/SKIP 만 존재) |
| `1` | FAIL 1건 이상 |
| `2` | 사용법 오류, 경로 없음, 리포트 저장 실패 |

→ CI(GitHub Actions)에서 `python3 run.py --no-html` 만 돌려 종료 코드로 회귀 감지가 가능합니다.

---

## 5. 점검 항목 (목표 20개)

판정 기준은 KISA 「주요정보통신기반시설 기술적 취약점 분석·평가 방법 상세가이드」의 **UNIX 서버** 항목을 따릅니다.
※ 항목 코드·번호는 널리 쓰이는 2021년판 기준이며, 최신 개정판(2025-12-24 배포본)에서는 번호나 판정 기준이 달라질 수 있습니다. 1주차 Day 5에 원문 PDF와 대조해 표를 확정합니다.

| 코드 | 점검 항목 | 중요도 | 점검 방법(요약) | 주차 | 구현 |
| --- | --- | --- | --- | --- | --- |
| U-01 | root 계정 원격 접속 제한 | 상 | `sshd_config` 의 `PermitRootLogin` | 1주 | ✅ |
| U-02 | 비밀번호 관리정책 설정 | 상 | `pwquality.conf` / `login.defs` 의 길이·복잡도 | 2주 | ⏳ |
| U-03 | 계정 잠금 임계값 설정 | 상 | `pam_faillock` / `pam_tally2` 의 `deny` | 2주 | ⏳ |
| U-04 | 비밀번호 파일 보호 | 상 | `/etc/passwd` 2번째 필드가 `x` 인지 | 1주 | ✅ |
| U-05 | root 이외의 UID가 `0` 금지 | 중 | `passwd` 전체에서 `uid=0` 계정 | 1주 | ✅ |
| U-06 | 사용자 계정 su 기능 제한 | 하 | `/etc/pam.d/su` 의 `pam_wheel` | 2주 | ⏳ |
| U-08 | 관리자 그룹에 최소한의 계정 | 하 | `/etc/group` 의 `sudo`·`wheel` 구성원 | 2주 | ⏳ |
| U-10 | 동일한 UID 금지 | 중 | `passwd` 의 UID 중복 | 2주 | ⏳ |
| U-11 | 사용자 shell 점검 | 하 | `/etc/shells`, `nologin`·`false` | 2주 | ⏳ |
| U-16 | /etc/passwd 소유자 및 권한 | 상 | `stat` — 소유자 root, 644 이하 | 1주 | ✅ |
| U-18 | /etc/shadow 소유자 및 권한 | 상 | `stat` — 소유자 root, 400 권장 | 1주 | ✅ |
| U-19 | /etc/hosts 소유자 및 권한 | 상 | `stat` — 소유자 root, 644 이하 | 3주 | ⏳ |
| U-23 | SUID, SGID, Sticky bit 파일 | 상 | 파일 탐색 + 허용 목록 비교 | 1주 | ✅ |
| U-25 | world writable 파일 점검 | 상 | 파일 탐색 (sticky 디렉터리 예외) | 1주 | ✅ |
| U-28 | 접속 IP 및 포트 제한 | 상 | `ss` 리스닝 포트 · `ufw`/`iptables` | 3주 | ⏳ |
| U-30 | UMASK 설정 관리 | 중 | `/etc/profile`, `login.defs` 의 `UMASK` | 3주 | ⏳ |
| U-52 | Telnet 서비스 비활성화 | 상 | `ss` 에 23/tcp 리스닝 여부 | 3주 | ⏳ |
| U-54 | 암호화되지 않는 FTP 비활성화 | 상 | `ss` 에 21/tcp · FTP 설정 | 3주 | ⏳ |
| U-63 | sudo 명령어 접근 관리 | 중 | `sudoers` 의 사용자·명령 제한 | 3주 | ⏳ |
| U-67 | 로그 디렉터리 소유자 및 권한 | 중 | `stat /var/log` | 3주 | ⏳ |

### 판정 정의

| 판정 | 의미 | 예 |
| --- | --- | --- |
| `PASS` | 기준 충족 | `/etc/shadow` 0400, 소유자 root |
| `FAIL` | 기준 위반 | `PermitRootLogin yes`, world writable 파일 존재 |
| `WARN` | 위반은 아니지만 정책 확인 필요 / 부분 점검 | `PermitRootLogin prohibit-password`(키 인증 root 허용), 탐색 항목 초과 |
| `SKIP` | 확인 불가 (파일 없음·권한 없음·점검 오류) | macOS 에 `/etc/shadow` 없음, root 아닌 사용자로 실행 |

---

## 6. 테스트

```bash
python3 -m unittest discover -v      # 표준 라이브러리만으로 실행
pytest -q                            # pytest 가 설치되어 있다면
```

```
Ran 86 tests in 0.024s
OK
```

테스트는 모두 **임시 디렉터리 기반**입니다. 실제 `/etc` 를 읽거나 바꾸지 않으며, 확인하는 것:

- `passwd` 파싱(정상·깨진 줄·주석), shadow 위임 여부, UID 0 중복
- 파일 권한 판정 규칙(`644`/`664`/`666`/`755`/`400`/`640` 등)을 순수 함수로 분리해 표 형태로 검증
- `sshd_config` 파싱(`=` 표기, 대소문자, 주석, `Match` 블록 이후 무시, 첫 값 우선)
- SUID/SGID·world writable 탐색(허용 목록, sticky bit 예외, `--max-entries` 초과 시 WARN)
- JSON/HTML 리포트 생성과 **HTML 이스케이프**(요약에 들어온 `<script>` 가 실행되지 않음)
- CLI 종료 코드(0/1/2), `--only`/`--exclude`, `--no-json`/`--no-html`, 없는 경로 오류

> 테스트용 파일은 현재 사용자 소유(uid ≠ 0)이므로, CLI 종단 테스트에서는 U-16/U-18 이 "소유자가 root 아님"으로 FAIL 이 되는 것이 정상입니다.

---

## 7. AI 활용 및 본인 검증 범위

이 프로젝트는 **AI로 초안을 만들고, 판정 기준과 결과를 사람이 검증하는 방식**으로 진행합니다. 포트폴리오에서 "AI를 썼다"는 사실을 숨기지 않고, **어디까지가 내 검증인지**를 밝히는 쪽이 신뢰를 얻는다고 판단했습니다.

| 구분 | 범위 | 상태 |
| --- | --- | --- |
| AI 초안 | 디렉터리 구조, 판정 모델, 점검 7개 코드, 테스트 케이스, README·체크리스트 초안 | 완료 |
| 본인 검증 | VM(Ubuntu 24.04)에서 `git clone` 후 실행, 항목별 판정이 실제 설정과 맞는지 수동 대조 | 1주차 Day 2~7에 수행 |
| 본인 검증 | KISA 원문 PDF와 판정 기준(허용 권한·값) 대조, 표의 코드/번호 확정 | 1주차 Day 5 |
| 본인 검증 | 오탐 사례 기록(배포판별 SUID 파일, sticky 디렉터리, 컨테이너 환경) | 4주차 보고서 |
| 본인 작성 | 각 점검의 "왜 이 기준인가" 주석, 실패 케이스 테스트, 전후 비교 스크린샷 | 진행 예정 |

**모든 코드는 읽고 설명할 수 있는 상태로 올립니다.** 설명할 수 없는 코드는 포트폴리오에 남기지 않습니다.

---

## 8. 프로젝트 구조

```
linux-baseline-auditor/
├── run.py                     # 설치 없이 실행하는 진입점 (python3 run.py)
├── pyproject.toml             # pip install -e . / 콘솔 스크립트 정의
├── README.md                  # 이 문서
├── WEEK1_CHECKLIST.md         # 1주차 Day 1~7 체크리스트 (하루 3~4시간)
├── src/linux_baseline_auditor/
│   ├── cli.py                 # 인자 파싱, 종료 코드
│   ├── engine.py              # 점검 실행, 예외 → SKIP
│   ├── models.py              # Status · CheckResult · Report · AuditContext
│   ├── reporters.py           # 콘솔 · JSON · HTML
│   ├── sysutil.py             # 안전한 읽기 전용 파일 접근
│   └── checks/
│       ├── base.py            # Check 뼈대 + 등록소(registry)
│       ├── account.py         # U-04 · U-05 · U-16 · U-18
│       ├── filesystem.py      # U-23 · U-25
│       └── service.py         # U-01
└── tests/                     # unittest 86개
```

새 점검 추가는 `checks/` 에 클래스를 하나 만들고 `@register` 를 붙이는 것으로 끝납니다.

---

## 9. 트러블슈팅 (실제로 겪은 것)

**(1) `python3 -m linux_baseline_auditor` 가 `ModuleNotFoundError`**
- 원인: `src/` 레이아웃이라 저장소 루트에서 패키지가 바로 보이지 않음.
- 해결: 루트에 `run.py` 를 두어 `sys.path` 를 잡아 주고, `python3 run.py` 로 실행. 설치형은 `pip install -e .` 사용.

**(2) SUID 점검이 정상 파일을 전부 "허용 목록 밖"으로 보고**
- 원인: 배포판마다 기본 SUID 실행 파일 목록이 다름(`/bin/chfn` vs `/usr/bin/chfn` 등).
- 해결: 내장 목록은 **참고용**으로 두고 `--suid-allowlist FILE` 로 자기 시스템 기준 목록을 넘기게 함. 목록에 없으면 FAIL 이 아니라 **WARN**(사람이 확인)으로 판정해 오탐이 점수를 망치지 않게 함.

**(3) world writable 점검이 `/tmp` 를 취약으로 보고**
- 원인: `/tmp`, `/var/tmp` 는 원래 공용 디렉터리.
- 해결: 디렉터리에 sticky bit(`1777`)가 있으면 정상으로 분류하고 개수만 근거에 남김.

---

## 10. 안전 및 윤리

- 이 도구는 **읽기 전용**입니다. 파일을 쓰거나 권한을 바꾸지 않습니다.
- **허가받은 시스템에서만** 실행하세요(본인 VM, 랩, 관리 권한을 위임받은 서버). 타인의 서버에 무단으로 실행하는 것은 정보통신망법 제48조 등에 저촉될 수 있습니다.
- 리포트에는 호스트명·파일 경로·설정값이 담깁니다. 공개 저장소나 블로그에 올릴 때는 **호스트명·IP·계정명을 가린 뒤** 올리세요(이 저장소에는 실제 운영 데이터가 없습니다).
- `FAIL` 은 침해 사실이 아니라 **설정이 기준과 다르다**는 뜻입니다. 최종 판단은 운영 정책과 함께 사람이 합니다.

---

## 11. 라이선스

MIT — [`LICENSE`](LICENSE) 참고.
점검 기준은 KISA 공공저작물(공공누리) 가이드를 참고했습니다.

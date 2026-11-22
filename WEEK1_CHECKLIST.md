# 🗓️ 1주차 체크리스트 — linux-baseline-auditor

- 대상: **완전 노베이스 입문자** (리눅스 명령을 거의 처음 쓰는 수준)
- 하루 투자 시간: **3~4시간** (막히는 날은 "오늘의 최소 완료"만 하고 넘어가도 됨)
- 이번 주 목표: **VM 리눅스 한 대를 직접 다루고, 저장소를 복제해 점검기를 돌려 보고, 점검 3개를 직접 다시 구현한다.**
- 이번 주 산출물: 실행되는 리포트 2개(`report.json`, `report.html`), `notes/day1~day4.md`, `docs/checklist-20.md`, 커밋 5개 이상

> ⏰ **오늘(11-22) 당장 시작할 첫 단계**
> 1. VirtualBox(Windows) 또는 UTM(macOS) 설치 → 2. Ubuntu **Server 24.04 LTS** ISO 다운로드(약 2.9GB, 받는 동안 1번 계속) → 3. VM 생성(2 vCPU / 4GB RAM / 25GB 디스크).
> ISO를 받아 두는 것만으로도 오늘의 절반입니다. 다운로드가 오래 걸리면 그 사이에 [OverTheWire Bandit](https://overthewire.org/wargames/bandit/) 페이지와 이 문서의 Day 2를 읽어 두세요.

---

## 이번 주 시간표

| 날 | 요일 | 주제 | 시간 | 완료 판정(측정 가능) |
| --- | --- | --- | --- | --- |
| Day 1 | 11-22 (일) | VM 설치 · SSH 접속 · 스냅샷 | 3.5h | 호스트에서 VM으로 SSH 로그인 성공, 스냅샷 1개 |
| Day 2 | 11-23 (월) | Bandit 0~10, git 기초, 저장소 실행 | 3.5h | Bandit 10 도달, VM에서 리포트 2개 생성, 테스트 86개 통과 |
| Day 3 | 11-24 (화) | 리눅스 권한 · 로그 읽기 | 3.5h | SSH 실패 3회를 `auth.log` 에서 찾아 캡처 |
| Day 4 | 11-25 (수) | 네트워크(포트·방화벽·패킷) | 3h | 3-way handshake 3줄 설명 + 패킷 캡처 1개 |
| Day 5 | 11-26 (목) | KISA 가이드 확보, 20항목 기준 확정 | 3h | `docs/checklist-20.md` 20행 완성 |
| Day 6 | 11-27 (금) | 점검 3개 직접 구현 + 테스트 | 4h | 직접 쓴 코드로 테스트 전부 통과 |
| Day 7 | 11-28 (토) | 항목 1개 추가, 전후 비교, README · 푸시 | 4h | public repo에 전후 스크린샷 2장, 커밋 5개 이상 |

**시간이 부족한 날의 우선순위:** Day 5(기준 확정) → Day 2(실행 성공) → Day 6(직접 구현). 나머지는 주말로 밀어도 됩니다.

---

## Day 1 (11-22 일) — VM 한 대 만들고 SSH로 들어가기

**목표:** 내 컴퓨터 안에 "실습용 리눅스 서버"를 만들고, 호스트에서 원격 접속해 명령을 실행한다.

| 시간 | 할 일 |
| --- | --- |
| 40분 | 가상화 도구 설치: Windows → VirtualBox, macOS → UTM(무료) |
| 20분 | Ubuntu Server **24.04 LTS** ISO 다운로드 시작(받는 동안 다음 단계 진행) |
| 60분 | VM 생성: 2 vCPU / 4GB RAM / 25GB 디스크 / 네트워크 NAT + 포트 포워딩 **호스트 2222 → 게스트 22** |
| 40분 | 설치 후 `sudo apt update && sudo apt install -y openssh-server` |
| 20분 | 호스트 터미널에서 `ssh -p 2222 <VM계정>@127.0.0.1` 접속 |
| 10분 | VirtualBox/UTM 스냅샷 이름 `clean-install` 저장 |

**완료 판정**
- [ ] 호스트에서 SSH 로그인 성공 (비밀번호 또는 키)
- [ ] VM 안에서 `python3 --version` 이 3.10 이상 출력
- [ ] 스냅샷 1개 존재 → 실수로 망가뜨려도 5분 안에 되돌릴 수 있는 상태

**막혔을 때**
- 포트 포워딩이 안 되면 네트워크를 **브리지 어댑터**로 바꿔 VM의 IP로 직접 접속.
- macOS UTM은 반드시 **Virtualize**(Apple Silicon이면 ARM64 ISO) 선택. Emulate는 매우 느립니다.
- Ubuntu 설치 중 "Install OpenSSH server" 체크박스를 놓쳤다면 위 `apt install` 로 해결.
- VM이 부팅되지 않으면 가상화 기능(BIOS의 VT-x/AMD-V)이 꺼져 있는지 확인.

---

## Day 2 (11-23 월) — Bandit 0~10, git, 그리고 저장소 첫 실행

**목표:** 리눅스 기본 명령에 손이 붙고, 남이 만든 저장소를 받아 실행할 수 있다.

### 1) OverTheWire Bandit 레벨 0~10 (약 2시간)

```bash
ssh bandit0@bandit.labs.overthewire.org -p 2220      # 최초 비밀번호: bandit0
```

- 레벨마다 **다음 레벨 비밀번호를 얻는 것**이 목적입니다. 각 레벨 15분, 안 풀리면 20분에서 멈추고 해설을 봅니다.
- 이 구간에서 반드시 손으로 써 보는 명령: `ls -la`, `cat`, `file`, `find`, `grep`, `sort`, `uniq`, `strings`, `base64 -d`, `du`, `ssh -p`
- 배운 명령과 막힌 지점을 `notes/day2.md` 에 적습니다(나중에 면접에서 "무엇을 어떻게 풀었나"의 재료).

> 🔒 Bandit 비밀번호는 학습용이지만 **저장소·블로그에 올리지 않습니다.** 개인 메모장에만.

### 2) git 기초 (30분)

```bash
git clone https://github.com/overwatch108912-ship-it/linux-baseline-auditor.git
cd linux-baseline-auditor
git status
# README.md 를 열어 오늘 한 일을 한 줄 추가한 뒤
git add README.md
git commit -m "docs: Day 2 진행 기록 추가"
git push
```

- `commit` = 내 컴퓨터에 기록, `push` = GitHub에 올리기. 둘의 차이를 말로 설명할 수 있으면 통과.

### 3) VM에서 점검기 실행 (1시간)

```bash
sudo apt install -y git python3
git clone https://github.com/overwatch108912-ship-it/linux-baseline-auditor.git
cd linux-baseline-auditor
python3 run.py --html report.html          # report.json, report.html 생성
python3 -m unittest discover -v            # 86개 테스트
```

**완료 판정**
- [ ] Bandit 10레벨 도달 (`bandit10` 접속 성공)
- [ ] VM에서 `report.json`, `report.html` 두 파일 생성, HTML을 열어 표 확인
- [ ] `Ran 86 tests ... OK` 출력
- [ ] 나의 첫 커밋이 GitHub에 올라감 (`git log --oneline` 에 본인 커밋)

**막혔을 때**
- `python3: command not found` → `sudo apt install -y python3`
- `Permission denied` 로 SKIP 이 많이 나오는 것이 정상입니다. root 권한이 필요한 항목은 `sudo python3 run.py` 로 다시 실행해 비교해 봅니다(결과가 달라지는 항목을 확인하는 것 자체가 공부).
- git push 인증이 막히면 GitHub의 **Personal Access Token** 또는 `gh auth login` 사용.

---

## Day 3 (11-24 화) — 권한과 로그: "읽을 줄 아는가"

**목표:** `/etc/passwd`, `/etc/shadow`, 권한 비트, 로그 파일을 **직접 열어 읽는다.** (관제 면접의 첫 질문)

### 1) 계정 파일 구조 (60분)

```bash
head -3 /etc/passwd            # 이름:비밀번호:UID:GID:설명:홈:셸
sudo head -3 /etc/shadow       # 이름:해시:마지막변경:최소:최대:경고:비활성:만료
ls -l /etc/passwd /etc/shadow  # 소유자·권한을 눈으로 확인
sudo stat -c '%a %U:%G %n' /etc/passwd /etc/shadow
```

- `x` 가 왜 있는지(= 해시를 shadow로 옮긴 것), 0400이 무엇을 막는지 **본인 말로 3줄** 적습니다.

### 2) 권한 실험 (60분)

```bash
cd ~ && echo secret > test.txt
chmod 644 test.txt && ls -l test.txt
chmod 664 test.txt && ls -l test.txt     # 그룹 쓰기 추가
chmod 777 test.txt && ls -l test.txt     # 전원 쓰기 — 왜 위험한가?
chmod u+s test.txt && ls -l test.txt     # SUID (s 표시)
chmod 000 test.txt && cat test.txt       # 읽기 권한이 없으면?
```

### 3) 로그 읽기 (60분)

```bash
ssh wronguser@localhost            # 일부러 3번 실패 (비밀번호 아무거나)
sudo tail -n 30 /var/log/auth.log  # "Failed password" 3줄 찾기
sudo journalctl -u ssh --since "10 min ago"
```

- 실패 로그에서 **출발지 IP, 사용자명, 시각, 실패 사유**를 읽어 냅니다.

**완료 판정**
- [ ] `auth.log`(또는 `journalctl`)에서 실패 로그인 3건을 찾아 스크린샷 저장
- [ ] `notes/day3.md` 에 (a) passwd/shadow 필드 설명 (b) 777이 위험한 이유 (c) SUID가 무엇인지 — 각 2~3줄
- [ ] 도구 판정과 손 확인이 일치: `python3 run.py --only U-16 U-18` 결과와 `stat` 값 비교

---

## Day 4 (11-25 수) — 네트워크: 포트 · 방화벽 · 패킷

**목표:** "지금 이 서버가 무엇을 열고 있는가"를 명령으로 확인하고, 패킷을 한 번 잡아 본다.

```bash
sudo apt install -y nginx ufw tcpdump
ss -tulnp                                  # 리스닝 포트 목록 (80/tcp = nginx)
sudo ufw status verbose
sudo ufw allow 22/tcp && sudo ufw enable   # SSH 먼저 허용해야 안 잠깁니다
sudo tcpdump -i any -n port 80 -c 10       # 다른 터미널에서: curl http://localhost
```

- 캡처한 패킷에서 **SYN → SYN/ACK → ACK** 순서를 찾아 3줄로 설명합니다.

**완료 판정**
- [ ] `ss -tulnp` 결과에서 80/tcp 가 nginx 프로세스인지 확인
- [ ] tcpdump 캡처 화면(또는 `-w cap.pcap` 파일) 1개 확보
- [ ] `notes/day4.md` 에 3-way handshake 3줄 설명 + `ufw` 규칙 3개 설명

**주의:** `ufw enable` 전에 SSH 포트를 허용하지 않으면 원격 접속이 끊깁니다. VM 콘솔에서 복구할 수 있으니 당황하지 말 것.

---

## Day 5 (11-26 목) — KISA 가이드로 20항목 기준 확정

**목표:** "내가 왜 644가 양호라고 판단하는가"의 근거를 원문에서 가져온다.

1. KISA 자료실에서 **「주요정보통신기반시설 기술적 취약점 분석·평가 방법 상세가이드」** PDF 다운로드
   → https://www.kisa.or.kr/2060204 (공공누리, 무료)
2. UNIX 서버 항목(67개) 중 이번 프로젝트의 20개를 고르고, README 표의 **코드·번호·중요도**를 원문과 대조
3. `docs/checklist-20.md` 에 항목마다 아래 4칸을 채웁니다.

| 코드 | 점검 명령(수동) | 양호 기준(원문 인용) | 조치 명령 | 내 코드 위치 |
| --- | --- | --- | --- | --- |
| U-16 | `stat -c '%a %U' /etc/passwd` | 소유자 root, 권한 644 이하 | `chmod 644 /etc/passwd` | `checks/account.py` |

**완료 판정**
- [ ] 20행 표 완성, 각 행에 "원문 인용"이 들어감
- [ ] 최신 개정판에서 번호가 다른 항목이 있으면 README에 메모
- [ ] 도구의 판정 문구와 원문 기준이 어긋나는 항목 목록화(있으면 고칠 목록)

---

## Day 6 (11-27 금) — 점검 3개를 직접 다시 구현

**목표:** 이미 있는 코드를 **읽고 → 지우고 → 다시 쓴다.** (AI가 만든 뼈대를 내 것으로 만드는 단계)

1. `src/linux_baseline_auditor/checks/account.py` 를 열어 `PasswdPermissions`(U-16)부터 읽습니다.
   - 포인트: `stat` 으로 권한을 얻고, **순수 함수** `evaluate_passwd_permissions(mode, uid)` 가 판정을 담당
2. 세 함수를 하나씩 **주석을 지우고 직접 타이핑**해서 다시 작성합니다: `evaluate_passwd_permissions`, `evaluate_shadow_permissions`, `RootUidOnly.run`
3. 테스트를 먼저 추가하고 코드를 고칩니다(실패 → 통과 경험).

```bash
python3 -m unittest discover -v
python3 run.py --only U-05 U-16 U-18 --html /tmp/check.html
```

**완료 판정**
- [ ] 세 함수를 스스로 작성해 테스트 전부 통과
- [ ] 코드에 "왜 644인가 / 왜 0400인가 / 왜 uid=0 을 보는가" 주석 3개 이상 (본인 문장)
- [ ] FAIL 케이스 테스트 1개 이상 직접 추가 (예: 666 권한 → FAIL)

**막혔을 때:** `print()` 로 중간값을 찍어 확인 → 그래도 모르면 테스트를 하나만 남기고 `-k` 로 좁혀 실행.

---

## Day 7 (11-28 토) — 항목 1개 추가, 전후 비교, 공개

**목표:** "취약 → 조치 → 양호"를 화면으로 남긴다. 면접에서 보여줄 것은 이 비교표입니다.

1. 항목 1개 추가 (30~60분): U-19 `/etc/hosts` 권한 — `PasswdPermissions` 를 복사해 경로만 바꾸면 됩니다. 테스트도 함께.
2. 취약 상태 만들기 → 리포트 → 조치 → 리포트 (60분)

```bash
# 1) 일부러 취약하게
sudo chmod 666 /etc/hosts
python3 run.py --only U-19 --html before.html
# 2) 조치
sudo chmod 644 /etc/hosts
python3 run.py --only U-19 --html after.html
```

3. README에 `before.png` / `after.png` (또는 GIF) 추가 + 실행 시간·항목 수 같은 정량 값 기입 (30분)
4. 커밋·푸시, 저장소 About에 한 줄 소개와 토픽 `security`, `python`, `kisa`, `blue-team` 설정 (30분)

**완료 판정**
- [ ] public 저장소에 전후 스크린샷 2장
- [ ] `python3 -m unittest discover` 통과 (테스트 88개 이상)
- [ ] 이번 주 커밋 5개 이상, README "구현 상태" 표가 실제 코드와 일치

---

## 주차 완료 자가 점검 (7개 중 6개 이상이면 2주차로)

- [ ] VM을 스냅샷으로 되돌려 복구할 수 있다
- [ ] `/etc/passwd` 와 `/etc/shadow` 의 차이를 3줄로 설명할 수 있다
- [ ] `chmod 644` / `664` / `777` 이 각각 누구에게 무엇을 허용하는지 즉답할 수 있다
- [ ] `auth.log` 에서 실패 로그인을 찾아 "무엇이 언제 어디서 실패했는지" 읽어 낼 수 있다
- [ ] `ss -tulnp` 로 열린 포트를 확인하고, 그중 하나를 근거와 함께 "불필요"라고 말할 수 있다
- [ ] 점검 코드 하나를 백지에서 다시 작성하고 테스트를 통과시켰다
- [ ] AI가 쓴 판정 기준 중 하나를 KISA 원문과 대조해 옳고 그름을 말할 수 있다

---

## 곁들여 볼 것 (선택)

- ⏰ **KISA 아카데미 K-Shield 주니어 기초과정(온라인 80시간, 무료, 19~34세)** 7차수 접수가 **11-23 마감** 예정입니다. 11-21 확인 시점에 academy.kisa.or.kr 가 "긴급 보안 점검"으로 접속 불가였으니, 11-23에 사이트가 열리면 바로 확인하세요. 기초과정 수료는 정규과정(2027 상반기 예상) 선발 가점입니다. — https://academy.kisa.or.kr
- 리눅스 기초가 너무 어렵게 느껴지면 드림핵 **Dream Beginners**(Tier 0 무료)를 Day 3 대신 2시간만 봐도 됩니다. — https://dreamhack.io/lecture/paths/dream-beginners

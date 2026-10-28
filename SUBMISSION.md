# HDU IS — Work 1 deliverable

Everything the assignment asks for, in one folder. Variant: **CVE-2021-21315**.

```
work1/                          ← this folder IS the git repository root
├─ app/                        Flask application
├─ tests/                      28 functional + security tests
├─ .github/workflows/ci.yml    SAST + SCA + tests on push/PR (at the root, so it runs)
├─ cve-fixes/                  reproduction + fix ("folder with your fixes")
│  ├─ Dockerfile               vulnerable image: systeminformation 5.3.0
│  ├─ Dockerfile.fixed         fixed image: 5.3.1 + application allow-list
│  ├─ docker-compose*.yml      the two environments, port 3000
│  ├─ app/server.js            the 40-line Express dashboard used in both
│  ├─ app/package.json         pins express + systeminformation 5.3.0
│  ├─ exploit/si_exploit.py    time-based PoC (payload `nginx; sleep 5`)
│  ├─ exploit/verify_fix.py    exploit-blocked + regression test
│  ├─ exploit/version_probe.js library-level A/B probe (5.3.0 vs 5.3.1)
│  └─ README.md                steps, root cause, fix, verification
├─ report/
│  ├─ Work1_Report_HDU_IS.pdf  the report (title page, all sections, control answers)
│  └─ build_report.py          regenerates the .docx from ../evidence
├─ evidence/                   captured real outputs
│  ├─ api_demo.txt             live curl transcript (11 requests)
│  ├─ bandit.txt               SAST result
│  ├─ pip-audit.txt            SCA result
│  ├─ pytest.txt               test suite
│  └─ si_probe.txt             library-level A/B evidence (5.3.0 vs 5.3.1)
├─ README.md                   the repository README (= the one you submit)
├─ requirements*.txt, Dockerfile, .env.example, run.py
└─ SUBMISSION.md               this file
```

## What was verified for real

| Item | How | Where |
|---|---|---|
| API works | live server + curl | `evidence/api_demo.txt` |
| SQLi blocked | `' OR 1=1 --` in `?q=` returns a literal match, not 3 rows | `evidence/api_demo.txt` §6 |
| XSS blocked | stored payload rendered as `&lt;script&gt;` | `evidence/api_demo.txt` §8 |
| Auth | 401 without token, 401 on tampered token, 401 after logout | `evidence/api_demo.txt` §4/9/10 |
| Tests | `pytest` → 28 passed | `evidence/pytest.txt` |
| SAST | `bandit -r app run.py -ll` → no medium/high | `evidence/bandit.txt` |
| SCA | `pip-audit -r requirements.txt` | `evidence/pip-audit.txt` |
| CVE-2021-21315 | real 5.3.0 vs 5.3.1 installed locally: arrays coerced, then rejected | `evidence/si_probe.txt` |
| Fix | 5.3.1 refuses non-strings; the app allow-list answers 400 | `evidence/si_probe.txt` + `cve-fixes/exploit/verify_fix.py` |

The library-level evidence was executed on this machine (Windows, Node 22)
against the real `systeminformation@5.3.0` and `@5.3.1`, and it is reproducible
anywhere Node runs. The end-to-end container run needs a POSIX shell (the
vulnerable call sites are Linux/macOS code paths) and Docker, which this machine
does not have — so those transcripts are marked as the reference environment's
expected output, and the compose files reproduce them in one command.

## Repository state

- Public repository: <https://github.com/WeiTao712/hdu-is-work1>
- Default branch `main`, CI green (bandit · pip-audit · pytest).
- Title page of the report is filled in: variant `CVE-2021-21315`,
  `Wei Tao`, `23320320` — no placeholders.

## What you still have to do (optional, for full marks on screenshots)

1. **Run the container lab on a machine with Docker** and replace the three
   screenshot placeholders in the report (§9, §10.4, §13.2):

   ```bash
   cd cve-fixes
   docker compose up -d --build                       # systeminformation 5.3.0
   python exploit/si_exploit.py --target http://127.0.0.1:3000
   docker compose down
   docker compose -f docker-compose.fixed.yml up -d --build   # 5.3.1 + allow-list
   python exploit/verify_fix.py --target http://127.0.0.1:3000
   ```

2. **Paste the two GitHub Actions screenshots** (the run page and one expanded
   log) into §6.3 of the report, replacing the placeholder there.

Nothing else is outstanding: the API, the tests, the pipeline, the CVE analysis
and the fix are all in place and pushed.

## Regenerating things

```bash
# report (after editing text or replacing evidence files)
python report/build_report.py

# API
pip install -r requirements-dev.txt && python run.py

# tests + scanners (same commands as CI)
pytest -v ; bandit -r app run.py -ll ; pip-audit -r requirements.txt

# library-level CVE evidence, no Docker needed
cd cve-fixes
npm i systeminformation@5.3.0 --prefix .tmp/old
npm i systeminformation@5.3.1 --prefix .tmp/new
node exploit/version_probe.js .tmp/old/node_modules/systeminformation
node exploit/version_probe.js .tmp/new/node_modules/systeminformation
```

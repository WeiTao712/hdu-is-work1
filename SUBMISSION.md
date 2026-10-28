# HDU IS — Work 1 deliverable

Everything the assignment asks for, in one folder.

```
work1/                          ← this folder IS the git repository root
├─ app/                        Flask application
├─ tests/                      28 functional + security tests
├─ .github/workflows/ci.yml    SAST + SCA + tests on push/PR (at the root, so it runs)
├─ cve-fixes/                  reproduction + fix ("folder with your fixes")
│  ├─ Dockerfile               vulnerable: systeminformation 5.3.0
│  ├─ Dockerfile.fixed         fixed: 5.3.1 + application allow-list
│  ├─ docker-compose*.yml      the two environments, port 3000
│  ├─ app/server.js            the 40-line Express dashboard used in both
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
│  ├─ si_probe.txt             library-level A/B evidence (5.3.0 vs 5.3.1)
│  ├─ exploit_vulnerable.txt   CVE reproduction transcript (reference env)
│  └─ exploit_fixed.txt        CVE blocked after the fix (reference env)
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
| CVE-2021-21315 | real 5.3.0 vs 5.3.1 installed locally: arrays coerced then rejected | `evidence/si_probe.txt` |
| Fix | 5.3.1 refuses non-strings; the app allow-list rejects the payload with 400 | `evidence/si_probe.txt` + `cve-fixes/exploit/verify_fix.py` |

The library-level evidence was executed on this machine (Windows, Node 22)
against the real `systeminformation@5.3.0` and `@5.3.1`, and it is reproducible
anywhere Node runs. The end-to-end container run needs a POSIX shell (the
vulnerable call sites are Linux/macOS code paths) and Docker, which this machine
does not have — the container transcripts are therefore marked as the reference
environment's expected output, and the compose files are provided to reproduce
them in one command.

## What you still have to do

1. **Push `secure-api/` to GitHub** (create the repo, then):

   ```bash
   cd secure-api
   git init && git add . && git commit -m "Work 1"
   git branch -M main
   git remote add origin https://github.com/<you>/hdu-is-work1.git
   git push -u origin main
   ```

   Wait for the first CI run, then copy the run URL and take the screenshots
   listed in the report (§6.3) and in the README (§4).

2. **Run the Vulhub part on a machine with Docker** and take the three
   screenshots referenced in the report (§9, §10.4, §13):

   ```bash
   git clone https://github.com/vulhub/vulhub.git
   docker compose up -d --build
   python exploit/si_exploit.py --target http://127.0.0.1:3000
   docker compose down
   cd <this folder>/cve-lab && docker compose -f docker-compose.fixed.yml up -d --build
   python exploit/verify_fix.py http://127.0.0.1:7860
   ```

3. **Fill in the title page**: variant number, surname + name, HDU number,
   group, date (they are red placeholders in `report/Work1_Report_HDU_IS.docx`).

4. Paste the GitHub Actions screenshots into §6.3 of the report and into §4 of
   `secure-api/README.md` (search for `SCA-OUTPUT` and the screenshot
   placeholders).

## Regenerating things

```bash
# report (after editing text or replacing evidence files)
python report/build_report.py

# API
cd secure-api && pip install -r requirements-dev.txt && python run.py

# tests + scanners
pytest -v ; bandit -r app run.py -ll ; pip-audit -r requirements.txt
```

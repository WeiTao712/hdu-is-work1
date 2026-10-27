# HDU IS — Work 1 deliverable

Everything the assignment asks for, in one folder.

```
work1/                          ← this folder IS the git repository root
├─ app/                        Flask application
├─ tests/                      28 functional + security tests
├─ .github/workflows/ci.yml    SAST + SCA + tests on push/PR (at the root, so it runs)
├─ cve-fixes/                  Vulhub reproduction + fix ("folder with your fixes")
│  ├─ docker-compose.yml       vulnerable: vulhub/gradio:4.12.0
│  ├─ docker-compose.fixed.yml + Dockerfile.fixed    the fix
│  ├─ app/app.py               the gradio app used in both
│  ├─ exploit/gradio_exploit.py  3-step PoC
│  ├─ exploit/verify_fix.py    exploit-blocked + regression test
│  └─ README.md                steps, root cause, fix, verification
├─ report/
│  ├─ Work1_Report_HDU_IS.pdf  the report (title page, all sections, control answers)
│  └─ build_report.py          regenerates the .docx from ../evidence
├─ evidence/                   captured real outputs
│  ├─ api_demo.txt             live curl transcript (11 requests)
│  ├─ bandit.txt               SAST result
│  ├─ pip-audit.txt            SCA result
│  ├─ pytest.txt               test suite
│  ├─ exploit_vulnerable.txt   CVE reproduced for real
│  └─ exploit_fixed.txt        CVE blocked after the fix
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
| CVE-2024-1561 | gradio 4.12.0 installed locally, exploit chain returned `win.ini` | `evidence/exploit_vulnerable.txt` |
| Fix | same chain against 4.13.0 → 404 at step 2, app still 200 | `evidence/exploit_fixed.txt` |

The gradio reproduction was executed on this machine (Windows, Python 3.11)
with the real `gradio==4.12.0` and `gradio==4.13.0`; only the `/etc/passwd`
target was replaced by `C:\Windows\win.ini`, since there is no `/etc/passwd`
on Windows. In the Vulhub container use `/etc/passwd` as in the README.

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
   cd vulhub/gradio/CVE-2024-1561 && docker compose up -d
   python exploit/gradio_exploit.py --target http://127.0.0.1:7860 --file /etc/passwd
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

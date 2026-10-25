# FinSight AI: Known Risks and Single Points of Failure (v3)

This is an awareness list first, and a fix guide second. Risks 1 to 6 are accepted for now. Risks 7 to 18 were found by reading the project statement, the config switch guide and the HLD diagram side by side. Risks 19 to 23 come from the scale and spike review (1000 to 5000 companies). Risks 24 to 30 come from the design review (roles, company partitions, chunking, reranking, document updates, data consistency, answer retry). Review this list before go-live and at each major release.

Each item has an owner and a review date. Fill these in.

What changed in v3: added risks 24 to 30 for the design review, added cost metering to risk 15, set the company partition rule in risk 19, moved reasoning loops out (they will be specified in their own phase), updated the role names, and renumbered the scale risks.

---

## How to read this file

**The setups**
- **Pilot config:** the low-cost starting values in the config switch guide. Used day to day while building and piloting.
- **Standard config:** the full setup (always-on database, WAF on, customer key, Textract, SnapStart, RDS Proxy, standby reader and so on). This is what the client sees and what the HLD diagram shows.

**Status labels**

| Label | Meaning |
|---|---|
| Accept | We know it, we chose to live with it for now |
| Fixed | The fix is done or being applied. Tests below prove it |
| Planned fix | We will fix it. Tests below prove it |
| Before onboarding | To be fixed or discussed with the client before they start |
| Later | Kept on the list. We will handle it in a later phase |
| Fix before go-live | Real gap. Must be closed and tested before real client data goes in |

**Test rules**
- Every test has a clear pass line. If there is no pass line, it is not a test.
- Run each test in staging first. Never test failure drills on production without a quiet period and a rollback ready.
- Save the result (date, who ran it, pass or fail) next to the owner row. A test with no saved result did not happen.

---

## Summary

| # | Risk | Status | Impact if it happens |
|---|---|---|---|
| 1 | Whole region outage | Accept | Product down, backups may be lost |
| 2 | Customer-managed encryption key | Accept | All data unreadable |
| 3 | Model gateway (LiteLLM) | Accept | No answers, fallbacks never run |
| 4 | Global router | Accept | Nobody can reach any region |
| 5 | Self-hosted fallback model | Accept | Last safety net fails |
| 6 | Login (Cognito) | Accept | Nobody can sign in |
| 7 | Slow first request after idle (pilot only) | Accept | First user waits about 15 seconds in pilot |
| 8 | Standard config gets less daily testing than pilot | Accept | A rarely used switch breaks at the client demo |
| 9 | Data residency gaps | Before onboarding | Legal breach, lost client |
| 10 | Hidden instructions inside uploaded files | Accept | Wrong answer that still looks cited |
| 11 | Numbers and scan accuracy | Fixed | Wrong figures shown with confidence |
| 12 | Question embedding has no backup | Accept | Questions fail while the embedding provider is down |
| 13 | Caches can show data to the wrong person | Fixed | Data leak, or removed users keep access |
| 14 | Database connections and parallel steps clash | Planned fix | Speed gain lost, or database overload |
| 15 | Cost can run away | Planned fix (metering), Later (limits) | Surprise bill, no view of spend per company |
| 16 | Logs and traces hold sensitive data | Later | Leak through the side door |
| 17 | Recovery is not proven, one bad account can delete everything | Fix before go-live | Permanent data loss |
| 18 | The golden test set is our only quality gate | Later | Bad releases pass unnoticed |
| 19 | Vector search layout and cells at scale | Planned fix | Slow or incomplete search, costly move later |
| 20 | One company's bulk upload blocks others | Planned fix | Other companies wait hours to upload |
| 21 | Embedding model change at huge scale | Later | Cost spike, slow search during reprocess |
| 22 | Fallback 3 too small at real traffic | Accept | Last safety net overloaded |
| 23 | User spikes (month-end, quarter close) | Planned fix | Crashes or one company hurts the rest |
| 24 | Role permissions are not defined | Planned fix | Wrong person sees or approves the wrong thing |
| 25 | Separate partition per company | Planned fix | Missing partition, slow schema changes, leak if a filter is skipped |
| 26 | Chunking and parsing choices | Planned fix | Wrong table numbers, higher cost |
| 27 | Cross-encoder rerank speed and hosting | Planned fix | Slow answers, or no answers if it is down |
| 28 | Document updates and changes spreading to other documents | Planned fix | Stale or conflicting numbers, high reprocess cost |
| 29 | Data consistency (ACID and BASE) is not stated | Planned fix | Half-finished uploads, duplicates, stale reads |
| 30 | Answer check, retry and learning | Planned fix (one retry), Later (learning) | Slow answers, or data learned across companies |

---

## Part A. Accepted risks (from v1)

### 1. Whole region outage

**Status:** Accept

**What can go wrong:** Everything runs in one region, and backups are in the same region. If the region goes down, the product is down. A region-wide loss could also take the backups.

**Why we accept it for now:** A second region adds cost and complexity, and data residency rules must be settled first.

**What we do instead:** Keep backups tested. Tell clients the product depends on one region.

**Fix when ready**
1. Settle data residency first (see risk 9). The second region must also be allowed for the client.
2. Copy backups to a second allowed region, encrypted with that region's own key.
3. Later, run the same setup in the second region and let the global router move companies over.

**Tests**
| Test | Pass line |
|---|---|
| Restore the latest backup into an empty test environment | Data is complete and the app works. Time taken is written down |
| Tell one test client in writing that we depend on one region | Written reply saved |
| After step 2 above: delete the primary backup copy in staging | Second-region copy restores fine |

| Owner | Review date |
|---|---|
| | |

---

### 2. Customer-managed encryption key

**Status:** Accept

**What can go wrong:** If the key is deleted or disabled, all encrypted data becomes unreadable.

**Why we accept it for now:** It is a rare, human-caused risk, not a traffic or outage risk.

**What we do instead:** Turn on deletion protection and the waiting period before deletion. Limit who can touch the key.

**Fix when ready**
1. Set the key deletion waiting period to the maximum (30 days).
2. Allow only two named people to change the key. Everyone else can only use it.
3. Add an alert on any "disable key" or "schedule deletion" event.

**Tests**
| Test | Pass line |
|---|---|
| In staging, try to schedule deletion with a normal developer login | Blocked |
| In staging, schedule deletion with an allowed login, then cancel it | Alert fires within 5 minutes, cancel works, data still readable |
| Review the list of people who can change the key every quarter | List matches the two named people |

| Owner | Review date |
|---|---|
| | |

---

### 3. Model gateway (LiteLLM)

**Status:** Accept

**What can go wrong:** All model calls go through it. If it fails, the 3 fallback models never get a chance to run.

**Why we accept it for now:** It is stateless and restarts quickly.

**What we do instead:** Watch it with an alert. Add a second copy later if it fails in practice.

**Fix when ready**
1. Run two copies in different zones behind one address.
2. Add a health check that sends a tiny test prompt, not only "is the process up".
3. Keep the gateway version pinned. Upgrade only through a normal release.

**Tests**
| Test | Pass line |
|---|---|
| Stop the gateway in staging during a question | User sees the "temporarily unavailable" message, never a raw error. Alert fires |
| Restart time | Back and healthy within the agreed time (write it down, for example 60 seconds) |
| After a second copy is added: stop one copy under load | No failed questions beyond the ones already in flight |

| Owner | Review date |
|---|---|
| | |

---

### 4. Global router

**Status:** Accept

**What can go wrong:** If it fails, nobody can reach any region.

**Why we accept it for now:** It is a simple lookup built on a managed service.

**What we do instead:** Keep it as simple as possible with no extra logic.

**Fix when ready**
1. Keep the company to region table small, versioned and backed up.
2. Add a "last known good" copy so a bad edit can be undone in minutes.
3. See risk 9 for where the router itself must live.

**Tests**
| Test | Pass line |
|---|---|
| Add a bad entry in staging (company pointing to no region) | Rejected before it goes live, or reverts on its own |
| Look up 100 test companies | Every one lands in the right region |
| Disable the router in staging | Alert fires and the error page is clear |

| Owner | Review date |
|---|---|
| | |

---

### 5. Self-hosted fallback model (fallback 3)

**Status:** Accept

**What can go wrong:** If it runs on a single machine, our final safety net is itself a single point of failure.

**Why we accept it for now:** Running two copies doubles the cost of a model that is rarely used.

**What we do instead:** Alert when it is used or when it is down. Show the "temporarily unavailable" message if every model fails.

**At scale:** see risk 22.

**Fix when ready**
1. Run it on two machines, or keep a second machine ready to start fast.
2. Check that a graphics machine can actually be started in our region when needed. These are sometimes hard to get.
3. Re-run the golden set on it after every model or prompt change.

**Tests**
| Test | Pass line |
|---|---|
| Block fallbacks 1 and 2 in staging, ask 20 questions | Fallback 3 answers, with citations. Alert fires. Trace is tagged |
| Block all models | Clear "temporarily unavailable" message, no crash |
| Golden set on fallback 3 alone | Meets its agreed minimum score (write the number down) |
| Machine restart drill | Back in the agreed time |

| Owner | Review date |
|---|---|
| | |

---

### 6. Login (Cognito)

**Status:** Accept

**What can go wrong:** If it is down, nobody can sign in.

**Why we accept it for now:** It is a managed AWS service that rarely fails, and we have no practical alternative.

**What we do instead:** Nothing. Users already signed in may keep working until their session ends.

**Fix when ready**
1. Write a short status message for the sign-in page so users know it is a login issue, not our app.
2. Turn on multi-factor sign-in for the System Admin and Executive Leadership roles.
3. Keep a break-glass admin process (written, tested) for the team, not for clients.

**Tests**
| Test | Pass line |
|---|---|
| Sign in as each of the 4 roles (Executive Leadership, Corporate Finance & Planners, Audit & Compliance, System Admin) | Each lands with the right access |
| Sign-in is blocked in staging, user already signed in | User keeps working until the session ends, then sees a clear message |
| Admin removes a user | User loses access (see risk 13 for how fast) |

| Owner | Review date |
|---|---|
| | |

---

## Part B. New risks found in this review

### 7. Slow first request after idle (pilot only)

**Status:** Accept

**What can go wrong:** In the pilot config the database pauses when idle, and the first request after a pause waits about 15 seconds. The same can happen with slow restores while SnapStart is off. The standard config keeps the database always on (`min_capacity_acu: 0.5`) and SnapStart on, so this does not apply to the client setup.

**Why we accept it for now:** It saves about $30 to $40 a month during the pilot, and the pilot config stays as it is.

**What we do instead:** Show the "waking up, please wait" message (`show_waking_message: true`) while the connection helper retries.

**Fix when ready**
1. Build the "waking up, please wait" message in the app and the retry in the connection helper.
2. Make sure scheduled jobs and pings never open database connections, so the pause can really happen.

**Tests**
| Test | Pass line |
|---|---|
| Pilot config: leave the database idle for the full pause time, then ask one question | Waking message is shown. Retries (5 tries, 5 seconds apart) cover the wake time and the answer arrives. No raw error |
| Pilot config: check the database at night | It actually paused (jobs and pings did not keep it awake) |
| Standard config: leave the system idle, then ask one question | No waking message, no long wait |

| Owner | Review date |
|---|---|
| | |

---

### 8. Standard config gets less daily testing than pilot

**Status:** Accept

**What can go wrong:** The HLD diagram shows the standard setup (WAF, SnapStart, ping, weekly republish, Textract, RDS Proxy, standby copy). The pilot config has several of these off or replaced by free tools. The client will see the standard config, but the team works on the pilot config day to day. A switch that is rarely turned on (for example RDS Proxy or the standby reader) can quietly break.

**Why we accept it for now:** The pilot config is the cheaper way to build, and the switch guide already says both paths must be written and tested.

**What we do instead:** Test the standard config before the client sees it.

**Fix when ready**
1. Make CI run the golden set against both the pilot config and the standard config.
2. Add a note on the HLD that it shows the standard setup, and which items are off in pilot.
3. Before the client introduction, do a full check of the standard config in staging.

**Tests**
| Test | Pass line |
|---|---|
| Golden set on the standard config in staging | Passes at the agreed score |
| Startup log check on the standard config | Every active switch value is logged and matches the standard values |
| Security check on the standard staging URL | WAF is attached, customer key is in use |
| Pilot and standard answers for the same 20 questions | Same answers and citations |

| Owner | Review date |
|---|---|
| | |

---

### 9. Data residency gaps

**Status:** Before onboarding

**What can go wrong:** The project statement says all data must stay in-country (in-region as fallback). The design has places where that may not hold:
- CloudFront is a global service. Pages and API calls can pass through edge locations outside the country.
- The global router holds the company to region list. If it runs outside the country, that list lives outside.
- Cognito stores user details. It may sit in a different region than the data.
- Some services we rely on (Textract, some model providers, the self-hosted model machines) may not exist in the in-country region.
- Each model provider in the gateway needs an in-region endpoint. "In-region" for a provider is not always "in-country".

**Plan:** These gaps will be fixed, or discussed with the client and agreed in writing, before the client is onboarded.

| Owner | Review date |
|---|---|
| | |

---

### 10. Hidden instructions inside uploaded files

**Status:** Accept

**What can go wrong:** Keeping uploaded documents correct and trustworthy is the company's responsibility, not the application's. Note what the app does check: the question the user types goes through the input gate (prompt trick and personal data checks). The words inside the document chunks found by search are not part of that check. So a file with a hidden instruction could still reach the model, and the answer would still show a real looking citation.

**Why we accept it for now:** The client owns their documents. The citation check, the personal data check and the "insufficient data" rule still apply to every answer.

**What we do instead:** Say it in the terms of use: the company confirms the documents are its own and trusted.

**Low-cost extra (optional)**
1. In the fixed prompt, tell the model that document text is data, never instructions.
2. Keep a few hidden-instruction test files in the golden set.

**Tests (optional, run once)**
| Test | Pass line |
|---|---|
| Upload 5 test files with a hidden instruction, then ask related questions | Answers are not changed by the instruction, or the output gate blocks them |

| Owner | Review date |
|---|---|
| | |

---

### 11. Numbers and scan accuracy

**Status:** Fixed

**What can go wrong:** The project statement says all calculations must be done by code (SQL or pandas) and never by the model, with at least 95% numeric accuracy. The HLD question flow showed no calculation step, so a model could do the maths from text chunks. Also, the pilot reads scans with a free tool (Tesseract), which is less accurate on numbers.

**Fix being applied**
1. Add a "calculate with code" step to the HLD question flow. The model may only repeat numbers from code results or cited chunks.
2. Extracted numbers get a confidence score. Low confidence goes to "needs review", not into answers.
3. Compare a sample of extracted numbers with the source for every new document type.
4. The standard config uses Textract for scans (`scan_reader: textract`). Run the tests below on that reader.

**Tests (prove the fix)**
| Test | Pass line |
|---|---|
| 100 numeric questions with known answers (totals, margins, differences, percent changes) | At least 95% exact or within the agreed tolerance |
| Same 100 questions, with the calculation step blocked | Answers say "insufficient data" instead of guessing |
| 50 scanned pages with known numbers: Tesseract versus Textract | Both scores written down. The reader used for clients meets the 95% line |
| Blurry or rotated scan | Marked "needs review", not read wrongly |

| Owner | Review date |
|---|---|
| | |

---

### 12. Question embedding has no backup

**Status:** Accept

**What can go wrong:** The answer models have 3 fallbacks each. The embedding model has none. Every question must be turned into a vector before search, and uploads need it too. If the embedding provider is down or slow, questions and uploads fail until it returns.

**Why we accept it for now:** A backup embedding path means embedding every document a second time, which can be a very large up-front cost for clients with many documents already embedded. Old and new vectors also cannot be mixed in one search.

**What we do instead:** The user accepts a short delay, a retry, or a clear failure message. If the client wants a different embedding model, they can change the primary embedding model (this functionality comes in a later phase, and needs the reprocess job from the switch guide).

**Fix when ready**
1. Retry a failed embedding call a few times with a short wait before giving up.
2. If it still fails, show "temporarily unavailable, please try again". Never show a raw error.
3. For uploads, keep the job in the retry list and finish it when embedding returns, with no duplicate chunks.
4. Alert the team when embedding fails or retries often.

**Tests**
| Test | Pass line |
|---|---|
| Block the embedding provider in staging, ask 10 questions | Retries happen, then the friendly message shows. No crash. Alert fires |
| Upload a file while embedding is blocked, then unblock | Job waits, finishes by itself, no duplicate chunks |
| Slow the embedding provider (not fully down) | Question still answers after a short delay, inside the agreed limit |
| After the model swap feature is built: change the primary embedding model on a test company | Reprocess job finishes first, old and new vectors are never mixed |

| Owner | Review date |
|---|---|
| | |

---

### 13. Caches can show data to the wrong person

**Status:** Fixed

**What can go wrong:** Two cache risks.
1. **Answer cache:** the key has company, question and a document stamp. If it does not also include what the user is allowed to see, a lower role could see an answer built from data meant for a higher role. A bug in the key could also show one company's answer to another.
2. **Role check cache (60 seconds):** Lambda functions keep nothing between requests, and each running copy has its own memory. "Clear that user's result right away" cannot reach every copy. A removed user may keep access up to the full wait time, on some copies.

**Fix being applied**
1. Add company, role and access scope into the answer cache key. Check the company again when reading the cache.
2. Keep the role cache in one shared place (the DynamoDB table), or check a small "role version" number on every call. When an admin changes a role, the number goes up and every copy sees it on the next call.
3. Cut `role_cache_seconds` to 0 for the System Admin and Executive Leadership roles if the test shows the delay is too long.
4. Delete cached answers when a document is deleted, not only when uploaded.

**Tests (prove the fix)**
| Test | Pass line |
|---|---|
| Two companies ask the same question | Never see each other's cached answer |
| Two different roles ask the same question on documents with different access | A role never gets a cached answer built from documents it cannot see |
| Remove a role, then send 50 calls in parallel for 2 minutes | Every call after the agreed time is denied. Write down the longest delay seen |
| Upload, change, then delete a document | Old answers are gone each time |
| Cache key unit test | Key changes when company, role or document stamp changes |

| Owner | Review date |
|---|---|
| | |

---

### 14. Database connections and parallel steps clash

**Status:** Planned fix

**What can go wrong:** The pilot config gives each function only 1 database connection, but "parallel steps" wants several database jobs at the same time (search, number calculations, history loading). With 1 connection they line up one after another, so the speed gain disappears. Raising the pool size without changing the safety rule could break the limit (reserved functions times connections). Also, uploads and questions share one small database (4 ACU ceiling). A big upload batch can slow every question.

**At scale:** risks 19 and 20 make this one bigger. The pilot values stay as they are.

**Fix plan** (the pilot config values stay as they are for now. The fix is made so the standard config works well for the client.)
1. Decide the number of connections one request needs (for example 3).
2. Update the validation rule to: reserved functions times connections per request must stay under the database limit.
3. Give upload and ingestion work a lower share than questions (separate small function limits, and a cap on how many ingestion jobs run at once).
4. In the standard config, RDS Proxy is on, which shares connections. Run the load test below on the standard config.

**Tests**
| Test | Pass line |
|---|---|
| Load test with `parallel_steps` on and pool size 1, then pool size 3 | Time to first word measured for both. Choose the better one that stays inside the limit |
| Upload 50 documents while 20 users ask questions (standard config) | Question times stay inside the agreed target |
| Push traffic past the cap | Friendly "busy" message, no raw errors, no database crash |
| Config check in CI | Rejects any combination that can use more connections than the database allows |

| Owner | Review date |
|---|---|
| | |

---

### 15. Cost can run away

**Status:** Planned fix (metering), Later (limits)

**What can go wrong:** The monthly budget per company is a soft limit that only sends an alert. Cost can still rise from a bug that repeats calls, a heavy user, retries, backup requests (two model calls), repeated reprocessing, or someone abusing the app while WAF is off. Today we also cannot see spend per company, per service, or for model calls. Shared AWS services (Lambda, API Gateway) cannot be split by company on the AWS bill.

**Plan (metering, now)**
1. One usage table, written by the model gateway, the upload jobs and the functions. Each row has company, service, units and estimated cost.
2. Services tracked: each model (tokens in and out), embedding tokens, Textract pages, rerank calls, Lambda time, storage, and database use.
3. Model spend comes from the gateway, per company, per model and per question type.
4. Shared services are split by company using request counts and run time.
5. Each month, compare the sum with the real AWS and provider bills.

**Plan for later (limits):** Handle it with tier level access (limits per plan tier) or other means, such as a daily limit per company and an account-wide budget alert.

**Tests**
| Test | Pass line |
|---|---|
| Run 100 questions for company A and 50 for company B | Usage table shows 100 and 50, with tokens and cost per model. Totals are within 5% of the provider usage page |
| Upload 20 documents for company A (some scanned) | Textract pages and embedding tokens are recorded for A only |
| Add up all company costs for a test month | Within 10% of the real bill (write down the gap) |
| Show the cost view for one company, per service | Numbers match the usage table. A viewer role cannot open it |
| When handled later: script that sends questions in a loop for one test company | The limit stops it, message is friendly, alert fires |
| When handled later: make the primary model fail on every call | Retries stop at the limit, cost per question stays under the agreed cap |

| Owner | Review date |
|---|---|
| | |

---

### 16. Logs and traces hold sensitive data

**Status:** Later

**What can go wrong:** X-Ray, CloudWatch and the audit table record every step. If they also record the question text, the document chunks or the answer, then financial data and personal data sit in logs that more people can read, may be kept forever, and may not follow the same company separation rules as the database.

**Plan for later:** Handle it by other means when time allows (for example log IDs and sizes instead of content, a keep time on every log group, and limited log access).

**Tests to add when handled**
| Test | Pass line |
|---|---|
| Ask a question containing a test name, account number and amount, then search all logs and traces | None of those values appear in plain text |
| Check every log group | Each has a keep time set |

| Owner | Review date |
|---|---|
| | |

---

### 17. Recovery is not proven, one bad account can delete everything

**Status:** Fix before go-live

**What can go wrong:** The HLD says backups are in the same region, encrypted, and "restore tested". Nothing says how long a restore takes, how much data we can lose, or what happens if a stolen or careless admin login deletes data, backups and keys together. The audit log has a write-once copy, but the backups do not say the same. Rebuilding the vector index after a restore could also take long.

**Fix when ready** (aim these at the standard config, which is what clients will use)
1. Agree two numbers with the client: how much data loss is acceptable (RPO) and how long a restore may take (RTO).
2. Make backups write-once or delete-protected, with delete only through a second approval.
3. Keep backups in a separate cloud account in the same approved region, if the client allows it.
4. Write the restore steps as a short runbook that covers the customer key and the standby copy, then practice them.

**Tests**
| Test | Pass line |
|---|---|
| Full restore drill on the standard config in an empty staging environment (database, files, vectors, config, key) | Finishes inside the RTO. Golden set passes on the restored copy |
| Check the data loss | Newest restored record is within the RPO |
| Try to delete a backup with a normal admin login | Denied |
| Repeat the drill every quarter | Result saved with date and name |

| Owner | Review date |
|---|---|
| | |

---

### 18. The golden test set is our only quality gate

**Status:** Later

**What can go wrong:** Every release, every fallback model, every speed switch and every model swap is approved by the same 100 questions. If the set is small, old or too easy, bad changes pass. If the team starts writing prompts to fit those 100 questions, the score rises but real answers do not improve.

**Plan for later:** Add more test questions over time, including real wrong answers found in the pilot (anonymised), "no answer in documents" questions and role-blocked questions. Keep one agreed minimum score per model in a file.

**Tests to add when handled**
| Test | Pass line |
|---|---|
| Break the system on purpose (for example, turn off the citation check in a test branch) | Golden set run fails the release |
| Count questions per type | Every type has at least the agreed minimum number |

| Owner | Review date |
|---|---|
| | |

---

## Part C. Scale and spike risks

**Size we are planning for (estimates):** 1000 to 5000 companies, 10 users each, 10,000 to 50,000 documents per company, and 20 to 50 pages each. That is roughly 200 million to 12.5 billion pages in total, and one large company can hold millions of searchable text pieces (chunks).

**Pilot rule for everything in this part:** keep the pilot cheap. One cell, and every new limit set low. These settings only cap work. They add no servers and no cost. Final numbers for the standard config are set after a load test.

Pilot values for the new settings (starting guesses):

```yaml
scale:
  cells: 1                                  # every company maps to cell 1
  vector_store: aurora_pgvector             # all search goes through one search interface
  ingestion_max_parallel_jobs_per_company: 1
  reprocess_max_parallel_companies: 1
  queue_priority: quick_first               # quick questions go before uploads and reprocess
  queue_max_wait_seconds: 5                 # after this, show the "busy" message
```

---

### 19. Vector search layout and cells at scale

**Status:** Planned fix

**What can go wrong:** All companies' vectors sit in one Aurora database, and search filters by company while it searches. At 100 million or more chunks this can get slow, or return too few results after filtering. The high end (over 100 TB of vectors) cannot fit in one shared database. Fixing the layout later means moving every stored vector.

**Why it matters:** This is the one choice that is very hard to undo.

**Fix when ready** (design now, build small, pilot stays at 1 cell)
1. Add a `cell` field. The global router maps each company to a region and a cell. In the pilot every company is in cell 1.
2. All vector search goes through one search interface in our code. The store name comes from config (`vector_store`), so it can be swapped later.
3. Choose the vector size (and any compression) now. Changing it later means re-embedding everything.
4. Inside a cell, each company gets its own partition of the large tables (see risk 25), with its own vector index. The company filter then happens first.
5. Later: small companies share a cell, very large ones get their own.

**Tests**
| Test | Pass line |
|---|---|
| Load test with fake data shaped like 1000 companies and 1000 documents each, then a larger run toward the high end | Search time for the largest company is inside the agreed target, and a request for the top 50 chunks returns 50 |
| Router test: every company maps to exactly one cell | A company with no cell, or two cells, is rejected at startup |
| Swap test in staging: point `vector_store` at a test store behind the same interface | Golden set gives the same answers |
| Company separation at scale: search as company A | Never returns a chunk of company B |

| Owner | Review date |
|---|---|
| | |

---

### 20. One company's bulk upload blocks others

**Status:** Planned fix

**What can go wrong:** The queue serves jobs in the order they arrive. One company loading 50,000 documents at once can make every other company wait hours for their uploads, and can slow live questions through the shared database.

**Fix when ready**
1. Per-company cap on how many ingestion jobs run at the same time (`ingestion_max_parallel_jobs_per_company`).
2. One queue per cell (the pilot has one queue because there is one cell).
3. Rate limit the bulk load, so it cannot use the whole database.
4. Show queue position or progress in the status function, so users know it is working.

**Tests**
| Test | Pass line |
|---|---|
| Company A uploads 500 test documents while company B uploads 1 | B's job starts within the agreed time (write it down) |
| Check running jobs during the bulk load | A never has more jobs running than its cap |
| Ask questions while the bulk load runs | Question times stay inside the agreed target |
| One bad file in the batch | It goes to the retry list and does not stop the rest |

| Owner | Review date |
|---|---|
| | |

---

### 21. Embedding model change at huge scale

**Status:** Later

**What can go wrong:** Changing the primary embedding model means re-embedding every chunk, which could be billions. Done all at once it causes a big cost spike and slows search. Old and new vectors must never be mixed in one search.

**Plan for later:** The model change feature comes in a later phase (see risk 12). The design rule to keep now: the model name and version are stored on every chunk (already in the switch guide), and the reprocess runs as a rolling job, a few companies at a time (`reprocess_max_parallel_companies`, pilot value 1), never all at once.

**Tests to add when the feature is built**
| Test | Pass line |
|---|---|
| Reprocess 3 test companies at a time while users ask questions | Question times stay inside the agreed target |
| Search during the reprocess | Old and new vectors are never mixed in one search |
| Rerun the reprocess job | No duplicate chunks |
| Roll back while old vectors still exist | Search works on the old vectors again |

| Owner | Review date |
|---|---|
| | |

---

### 22. Fallback 3 too small at real traffic

**Status:** Accept

**What can go wrong:** The self-hosted fallback model is a small last-resort path. At real traffic it cannot carry the load if the outside providers fail together.

**Why we accept it for now:** In the pilot there is little traffic, and a bigger machine would add cost.

**What we do instead:** Treat it as a last resort only. When it is full, show the "busy, please try again" message, and alert the team when it is used.

**Tests**
| Test | Pass line |
|---|---|
| Block fallbacks 1 and 2, then send more traffic than fallback 3 can handle | Extra requests get the busy message. No crash, no line that grows forever. Alert fires |
| Golden set on fallback 3 under load | Answers keep citations and meet its agreed minimum score |

| Owner | Review date |
|---|---|
| | |

---

### 23. User spikes (month-end, quarter close)

**Status:** Planned fix

**What can go wrong:** A sudden wave of users can overload the database first, then the model provider limits and the fallback model. Without a plan, the result is crashes, raw errors, or one company slowing everyone else.

**Fix when ready**
1. A short waiting line in front of the heavy work. After `queue_max_wait_seconds`, show the "busy, please try again" message.
2. Priority: quick questions go first, then uploads and reprocess (`queue_priority: quick_first`).
3. Fair share per company, so one company's spike cannot use all capacity.
4. Keep uploads apart from questions (see risk 20).
5. Raise capacity ahead of known peaks (month-end, quarter close, board meetings) through a normal config pull request, then lower it afterwards.
6. The answer cache already helps when many people ask the same question.

**Tests**
| Test | Pass line |
|---|---|
| Push traffic to 2 times the planned capacity for 10 minutes | No crash, no raw errors. Extra requests get the busy message |
| One company sends 10 times its normal traffic | Other companies stay inside the agreed target |
| Fill the upload and reprocess queue, then ask quick questions | Quick questions are answered first, inside the target |
| Raise limits by pull request before a test peak, then lower them | Startup logs show the new values each time. Nothing breaks |
| Stop the traffic | Normal response times return within the agreed time |

| Owner | Review date |
|---|---|
| | |

---

## Part D. Design review decisions

These risks come from the design review. Decisions already taken: 4 role groups with 10 users per company, one partition per company, a trimmed chunking strategy, a cross-encoder rerank step, cost metering, document categories and upload types, stated consistency rules, and a limited answer retry. They are mostly design rules and tests, so they add almost no cost to the pilot.

---

### 24. Role permissions are not defined

**Status:** Planned fix

**What can go wrong:** The roles are now 4 groups with 10 users per company: Executive Leadership (CEO, CFO, VP of Finance), Corporate Finance & Planners (4 users), Audit & Compliance (2 users), and System Admin (1 user). Nothing yet says what each role can see or do, and document categories (risk 28) add a second axis. A wrong setting could let the System Admin read financial data, let the wrong role approve a recommendation, or hide documents from Audit & Compliance.

**Proposed permissions (confirm with the client)**
| Role | Ask questions | Upload and update documents | Approve recommendations | Manage users and settings | See audit logs |
|---|---|---|---|---|---|
| Executive Leadership | Yes | No | Yes | No | No |
| Corporate Finance & Planners | Yes | Yes | No | No | No |
| Audit & Compliance | Yes (read only, all categories) | No | No | No | Yes |
| System Admin | No financial content | No | No | Yes | Yes |

**Fix when ready**
1. Confirm the table, and the document categories each role may see.
2. Keep roles in Cognito groups. Keep permissions in one table or config, not spread through code.
3. Enforce at the API, and again in the data layer (search filters by allowed categories).
4. The answer cache key already includes the role (risk 13).

**Tests**
| Test | Pass line |
|---|---|
| Table test: every role, every action, every document category | Allowed or denied exactly as the confirmed table. 100% match |
| Call the API directly, skipping the screen | Same result as through the screen |
| System Admin asks a question about financial data | Denied, or no financial content is shown (as the table says) |
| Only Executive Leadership approves a recommendation | Any other role is denied, and the attempt is logged |
| Change a user's role | New access applies within the agreed time (risk 13) |

| Owner | Review date |
|---|---|
| | |

---

### 25. Separate partition per company

**Status:** Planned fix

**What can go wrong:** Each company gets its own partition of the large tables (documents, chunks, vectors, metrics) inside its cell. This keeps companies apart by design and gives each one its own vector index, which fixes the slow filtered search in risk 19. It also brings risks: a partition not created at onboarding (uploads fail), a schema change that must run on every partition (up to about 1,000 per cell), a query that forgets the company filter and scans every partition, and slow index builds.

**Why this and not fully separate tables:** Separate tables for 1,000 to 5,000 companies would mean tens of thousands of tables, and every schema change would have to run on each one. Partitions give the same separation with one schema.

**Fix when ready**
1. One parent table per kind and one partition per company. An onboarding job creates them, and must finish before the first upload.
2. Keep the row-level rule on as a second lock.
3. Every query must include the company. A test build rejects any query without it.
4. Schema changes run through a migration tool that loops over all partitions, and is tested on 1,000 test partitions.
5. When a company leaves, drop its partitions and its S3 folder, then prove it is gone.

**Tests**
| Test | Pass line |
|---|---|
| Onboard 1,000 test companies | All partitions exist. Time taken is written down |
| Search as company A with the company filter removed (test build) | The row-level rule still blocks other companies' rows |
| Look at the query plan for a search | Only that company's partition is read |
| Run a schema change on 1,000 partitions in staging | Finishes in the agreed time, no failed partition |
| Delete a test company | Partitions and S3 folder are gone. Backups follow the retention rule |
| Search the largest test company | Time is inside the agreed target (risk 19) |

| Owner | Review date |
|---|---|
| | |

---

### 26. Chunking and parsing choices

**Status:** Planned fix

**Decision:** Layout-aware parsing chosen per page (table pages to the table-aware reader, plain text pages to the cheap reader). Chunking by structure (headings, paragraphs, tables kept whole). Parent-child chunks: the small chunk is searched, and its parent section is stored as text with no extra vector. A rule-based context header and rich metadata on every chunk. Not used: semantic chunking, and model-written context for every chunk.

**What can go wrong:**
- A table page goes to the cheap reader and numbers come out wrong.
- A table is split across chunks.
- Units, currency or period are missing, so thousands and millions get mixed up.
- The parent sent to the model is too big, so prompts and model cost grow.
- Smaller chunks double the vectors. Monthly cost rises about 30% (Low) and 70% (High).
- Model-written context for every chunk would cost about $340 K (Low) and $21 M (High). Keep it off. It can be tried later for a few high-value document categories.
- The parsing tool must run in the approved region.

**Fix when ready**
1. A page router detects table and layout pages before reading.
2. Never split a table. Also store its numbers as structured rows, so code can calculate with them (risk 11).
3. A chunk is saved only with company, period, document category, currency, units, page and table id. If any is missing, mark it "needs review".
4. Child chunk about 500 tokens. Parent is the section or page text.
5. Keep the chunk text sent to the model within the token budget per question.
6. Make the strategy a config switch, so it can be compared on the golden set.

**Tests**
| Test | Pass line |
|---|---|
| 100 tables with known numbers | At least 95% of cells exact, and no table split |
| 200 mixed pages with known types | Pages sent to the right reader at the agreed rate (write it down) |
| Documents in thousands and in millions | Answers show the right unit |
| Golden set against a plain recursive chunking baseline | Score is not lower. Prompt tokens per question stay within the budget |
| Vectors per page and embedding tokens per page | Within the agreed numbers (cost check) |
| Metadata check on every saved chunk | All fields present, or marked "needs review" |

| Owner | Review date |
|---|---|
| | |

---

### 27. Cross-encoder rerank speed and hosting

**Status:** Planned fix

**Decision:** The rerank step is a cross-encoder that scores the question against each of the top 50 chunks. It runs in the approved region, and its score also feeds the "Enough evidence?" check. There is no second cross-encoder after it.

**What can go wrong:**
- It is slow. The simulation puts p95 first response at about 2.8 s against a 3 s target, so there is only about 0.2 s of room (rerank is about 250 ms typical, 400 ms bad case).
- It is down, so every question fails.
- It runs outside the approved region.
- The evidence threshold is wrong, so there are too many "insufficient data" answers, or wrong answers.
- A paid rerank service costs about $2 per 1,000 searches (estimate), or about $8 K a month at the High size.

**Fix when ready**
1. Host it in the approved region. Score the chunks in parallel batches (already in the config guide).
2. If it is down, fall back to the search order, tag the trace and alert. Accuracy may drop.
3. Set the evidence threshold using the golden set, including questions that have no answer.
4. Keep the number of chunks scored in config (`rerank_top_n`).

**Tests**
| Test | Pass line |
|---|---|
| Rerank 50 chunks at peak QPS | p95 at or under 400 ms |
| Block the reranker in staging, ask 20 questions | Questions are answered in search order, trace is tagged, alert fires |
| 50 questions with no answer in the documents | At least the agreed share answer "insufficient data" |
| Golden set with the reranker on | Score is not lower than before |
| Region scan (risk 9) | Reranker endpoint is in an approved region |

| Owner | Review date |
|---|---|
| | |

---

### 28. Document updates and changes spreading to other documents

**Status:** Planned fix

**What can go wrong:** Today there is no rule for updated documents. An update uploaded as "new" creates duplicates, and two versions may disagree (draft and final). Reprocessing everything for a small change wastes money. A restated number in one document also leaves other documents, KPIs, forecasts, alerts, dashboards, cached answers and approved recommendations out of date. Users may pick the wrong upload type.

**Fix when ready**
1. **Upload form:** a Document Category (for example invoice, bank statement, financial statement, budget, contract, board report, set with the client) and an Upload Type: New, Update (pick the document it replaces) or Delete. Also a status: draft or final.
2. **Duplicate check:** compare file hash, name, company and period. Suggest "Update" when it finds a match.
3. **Update flow:** hash every page and skip unchanged pages (no Textract, no embedding). Hash every chunk and embed only the changed or new ones. Mark removed chunks inactive. This needs stable chunk ids from structure-based chunking (risk 26).
4. **Versions:** every update makes a new version. Old versions are kept for audit. Answers use the latest final version and cite the version.
5. **Cascade:** recompute affected metrics by code, clear cached answers, mark dependent forecasts, alerts and dashboards as stale, flag other documents for the same company and period as "may be affected" for review, and tell the approvers of recommendations that used the old numbers. Never edit other documents automatically.
6. **Conflicts:** if two documents give different figures for one metric and period, prefer final over draft and newer over older, and show both with citations.
7. **Delete:** soft delete with a retention rule, then purge chunks, metrics and cache entries.

**Tests**
| Test | Pass line |
|---|---|
| Update a document where 10% of the pages changed | Textract pages and embedding tokens used are at most 15% of a full reprocess. Unchanged chunk ids stay the same |
| Insert a paragraph at the top of a document | Only the chunks near it change, not all of them |
| Update a document with a restated revenue number | The answer gives the new number and cites the new version. Old version is viewable. KPI is recomputed, cache is cleared, forecast is marked stale, approver is notified |
| Upload the same file twice | Warning shown, no new chunks |
| Upload as "New" when a matching document exists for the same period | System suggests "Update" |
| Draft and final with different numbers | Final is used, with a note, and both are cited |
| Delete a document | No chunk, metric or cache entry is left. Audit entry exists |
| Kill the update job halfway, then rerun | Final state is the same as an uninterrupted run (risk 29) |

| Owner | Review date |
|---|---|
| | |

---

### 29. Data consistency (ACID and BASE) is not stated

**Status:** Planned fix

**What can go wrong:** The design never says which data must always be exactly right (ACID) and which may lag for a moment (BASE). S3, the database, DynamoDB, the queue, the cache and the standby reader cannot share one transaction. The queue can deliver a message twice, and the standby reader can be slightly behind. Results: a document shown as "ready" with some chunks missing, duplicate chunks and double cost, a role change not seen, a search right after upload that misses the new file, or a cached answer older than its document.

**Rules**
| Data | Where | Rule |
|---|---|---|
| Documents, chunks, vectors, metrics, versions | Aurora | ACID. One transaction per document version. Visible only when the whole version is saved |
| Roles, permissions, role version | DynamoDB and Aurora | Strongly consistent reads. Privileged roles use no cache |
| Audit log | Aurora and the write-once copy | ACID, append only |
| Job status | Aurora | ACID. Updated in the same transaction as the results |
| Answer cache | DynamoDB | BASE is fine. Entries stop being used the moment the document stamp changes. The stamp is read strongly consistent |
| Chat history, progress screens, counts | DynamoDB or the standby reader | BASE is fine. A lag of a few seconds is accepted |
| Raw files | S3 | Saved before the job is queued |
| Queue messages | SQS | Delivered at least once. Every job must be safe to repeat (job id, upsert on chunk id) |

**Fix when ready**
1. A job state machine: received, stored, processing, committed, failed.
2. "Ready" is shown only after commit. Reads right after an upload use the main database until the standby copy has caught up.
3. The document stamp changes in the same transaction as the document.
4. Every ingestion step uses job ids and upserts, so a repeat does no harm.

**Tests**
| Test | Pass line |
|---|---|
| Kill an ingestion job at each step (read, embed, write) and rerun | Same chunks as a clean run. No duplicates, none missing |
| Send the same queue message twice | One set of chunks, cost counted once |
| Search right after an upload, using the standby reader | Document is found, or the user sees "still processing". Never a silent miss |
| Force a database failover during an upload | No half-visible document |
| Change a role, then send 50 parallel calls | Denied after the agreed time (risk 13) |
| Update a document, then ask the same question again | New answer, never the old cached one |
| Check the audit log after each test above | An entry exists for every saved change |

| Owner | Review date |
|---|---|
| | |

---

### 30. Answer check, retry and learning

**Status:** Planned fix (one retry), Later (learning)

**Decision:** In the early phases, when an answer fails the checker (missing citation, a number that does not match a code result or a cited chunk, personal data), the system retries once, then answers "insufficient data". There is no model judge on every question. Full agentic loops will be specified in their own phase. Learning means human-reviewed feedback that grows the golden set and tunes prompts and reranking offline, through the release gate.

**What can go wrong:**
- A retry adds time and cost to that question. A cheap judge on every question would add about 15% to the model cost, and a strong judge about 150%.
- Sentences already shown cannot be taken back, because the output gate shows each sentence as it passes.
- Retries could repeat without end.
- Learning from one company's data could leak into another company's answers.
- Bad feedback could spoil the golden set.

**Fix when ready**
1. Allow a retry only before the first sentence is shown, and only if the time used so far is under the agreed limit. If a check fails later, stop with a clear message.
2. At most one retry. Log it on the trace.
3. Keep feedback per company. A person reviews it before it can enter the golden set, and it is anonymised first.
4. No model training on client data without written consent. No sharing of learned content between companies.

**Tests**
| Test | Pass line |
|---|---|
| Force an answer with a missing citation | Exactly one retry, then a good answer or "insufficient data". Never two retries |
| 100 forced failures | Added time and cost per retry written down. First response with a retry is inside the agreed limit |
| Failure after the first sentence is shown | No restart. The answer ends with a clear message |
| Feedback on company A, then ask the same question as company B | B's answer does not change |
| Feedback that nobody reviewed | Never enters the golden set |

| Owner | Review date |
|---|---|
| | |

---

## Go-live test checklist

Run in this order. Do not skip. Tick only with a saved result. Items marked "Later" are not part of this checklist.

| Step | Risks covered | Done |
|---|---|---|
| 1. Sign off the data location list with the client, or agree the gaps in writing | 9 | |
| 2. Run the golden set, startup log check and security check on the standard config | 8 | |
| 3. Run the 100 numeric questions and the scan reader test | 11 | |
| 4. Role permission table test, then cache key tests and the role removal test under parallel calls | 13, 24 | |
| 5. Partition tests: 1,000 test companies, filter removed, query plan, schema change | 19, 25 | |
| 6. Table accuracy, page routing and units tests | 26 | |
| 7. Rerank speed, down drill and evidence threshold | 27 | |
| 8. Document update tests: delta, cascade, duplicates, delete | 28 | |
| 9. Consistency drills: kill jobs, duplicate messages, standby reader, failover | 29 | |
| 10. Block the embedding provider and test retry and message | 12 | |
| 11. Forced answer failures: one retry only, no cross-company learning | 30 | |
| 12. Load test shaped like the planned size (fake data, many companies), including fair bulk loading | 14, 19, 20 | |
| 13. Spike test: push past the limit, check nothing crashes and other companies are unaffected | 22, 23 | |
| 14. Cost metering check against the real bills | 15 | |
| 15. Restore drill on the standard config against the agreed RPO and RTO | 1, 17 | |
| 16. Failure drills: gateway, fallback 3, login, router, key | 2, 3, 4, 5, 6 | |
| 17. Pilot only: idle wake-up test with the waking message. Standard: confirm always-on | 7 | |
| 18. Fill in every owner and review date | All | |

## Notes

- Managed AWS parts that already spread across zones (S3, DynamoDB, Lambda, and the database with a standby copy) are not listed here.
- If a risk becomes more likely or a client asks for stronger guarantees, move it from this list into the config switch guide as a real switch.
- Risks marked "Later" (15 limits, 16, 18, 21, 30 learning) stay on the list so they are not forgotten. Review them at each major release.

**Framework:** pytest (already in `requirements.txt`). Test file: `scaffold/tests/test_api.py`. Run from the `scaffold/` directory with the virtual environment active:

```bash
pytest tests/ -v
```

**Required test coverage per endpoint:**

| Endpoint | Cases to cover |
|---|---|
| `POST /api/qr/create` | valid URL → 200 with token/short_url/qr_code_url; URL > 2048 chars → 422; non-http/https scheme → 422; blocked domain → 422 |
| `GET /r/{token}` | active token → 302 with correct `Location`; soft-deleted token → 410; expired token → 410; token that never existed → 404; redirect records a `ScanEvent` row |
| `GET /api/qr/{token}` | active token → 200 with correct fields; soft-deleted token → 404; non-existent token → 404 |
| `PATCH /api/qr/{token}` | update `original_url` → 200, redirect now resolves to new URL; set `expires_at` in the past → subsequent redirect returns 410; non-existent token → 404 |
| `DELETE /api/qr/{token}` | active token → 200, subsequent redirect returns 410; non-existent token → 404 |
| `GET /api/qr/{token}/image` | active token → 200 `image/png`; non-existent or deleted token → 404 |
| `GET /api/qr/{token}/analytics` | returns `total_scans` int and `by_date` list; non-existent token → 404 |

**Edge cases that must have explicit tests:**

- **Expired token** — insert a `UrlMapping` with `expires_at` set one second in the past; assert `GET /r/{token}` returns 410.
- **Deleted token** — create via API then `DELETE`; assert `GET /r/{token}` returns 410 and `GET /api/qr/{token}` returns 404.
- **Non-existent token** — use a 7-char string that was never inserted; assert `GET /r/{token}` returns 404 and `GET /api/qr/{token}` returns 404.
- **Cache invalidation** — patch or delete a token that was previously fetched (cache populated); assert the next redirect reflects the updated state, not the stale cache entry.

---

## Feedback Loop

The agent must follow this loop strictly — no step may be skipped:

```
1. Implement (or fix) the code.
2. Run: pytest tests/ -v
3. If any test fails:
   a. Read the full pytest output.
   b. Identify the root cause — do not guess.
   c. Fix only the failing code path.
   d. Go to step 2.
4. If all tests pass → proceed to Definition of Done check.
```

**Rules:**

- Never mark a task complete while any test is red.
- Never silence a test (skip/xfail) to make the suite green — fix the code.
- If a fix causes a previously passing test to fail, treat the regression as a new failure and loop again.
- Do not move to the next endpoint until the current endpoint's tests are fully green.

---

## Definition of Done

The implementation is complete only when **all** of the following are true simultaneously:

- [ ] `pytest tests/ -v` exits 0 with no skipped or xfailed tests.
- [ ] Every endpoint listed in the spec exists and returns the documented HTTP status codes.
- [ ] Redirect behavior exactly matches the 302/404/410 rule: `GET /r/{token}` returns 302 for active, 410 for deleted or expired, 404 for never-existed — with no exceptions.
- [ ] `GET /api/qr/{token}` returns 404 for both deleted and non-existent tokens (not 410).
- [ ] The in-memory cache is invalidated on every `PATCH` and `DELETE` so stale redirects are impossible.
- [ ] A `ScanEvent` row is written for every successful 302 redirect.
- [ ] The frontend build (`npm run build`) completes without errors and is served correctly by FastAPI at `/`.

---

## Non-Goals

The following must **not** be added, even if they seem like natural improvements:

| Item | Reason excluded |
|---|---|
| Authentication / API keys | Out of scope for a prototype; adds complexity with no spec requirement |
| Rate limiting | No abuse-prevention requirement exists in the spec |
| Distributed caching (Redis, Memcached) | SQLite + in-memory dict is the specified stack |
| Message queues or async workers | Synchronous request handling is sufficient for the prototype |
| Multi-database support or migrations tooling (Alembic) | `Base.metadata.create_all` on startup is the specified approach |
| User accounts or ownership model | Tokens are anonymous by design |
| Custom short-URL slugs | Token generation algorithm is fixed in the spec |
| HTTPS termination or TLS config | Handled outside the app (reverse proxy / hosting layer) |
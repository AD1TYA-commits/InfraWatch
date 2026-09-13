# Authentication & Roles

## The JWT flow

InfraWatch uses stateless JWT bearer authentication — no server-side session
store.

1. **Register** (`POST /api/auth/register`) — takes `email`, `password`
   (minimum 8 characters, enforced server-side), `role`
   (`"analyst"` or `"contractor"`), `full_name`, optional `organization`.
   The password is hashed with bcrypt (via `passlib`'s `CryptContext`,
   `app/auth.py`) before it ever touches the database — the raw password is
   never stored or logged. A duplicate email is rejected with 409.
2. **Login** (`POST /api/auth/login`) — takes `email`/`password`, verifies
   the hash with `passlib`'s `verify_password`, and returns a signed JWT.
3. **The token** — issued by `create_access_token()`, signed with
   `JWT_SECRET_KEY` using `HS256` (`python-jose`), and carries `sub` (user
   id), `role`, `email`, and an `exp` claim. Default lifetime is 7 days
   (`JWT_EXPIRE_MINUTES`, `backend/app/config.py`).
4. **Every subsequent request** sends the token as
   `Authorization: Bearer <token>`. `get_current_user()` decodes and
   verifies it (`app/auth.py`), reloads the user row from the database (so a
   deleted/disabled user is rejected even with a still-valid token), and
   makes it available to the endpoint via FastAPI's dependency injection.
5. **Logout** is purely client-side — the frontend discards the token from
   `localStorage`. There is no server-side revocation list; a token remains
   valid until it expires.

There is no refresh-token flow, no password-reset flow, and no rate
limiting on login/register — all reasonable next additions before any
production use, none built yet (see the Limitations section of the root
README).

## Password hashing

`bcrypt` via `passlib.context.CryptContext(schemes=["bcrypt"])`. Confirmed by
a dedicated test (`test_password_is_hashed_not_plaintext`) that the stored
`hashed_password` is never equal to the plaintext and always starts with the
`$2b$` bcrypt prefix. `requirements.txt` pins `bcrypt<4.1` specifically
because passlib 1.7.4's bcrypt handler breaks against bcrypt≥4.1's removed
`__about__` attribute — see the comment there if this ever needs revisiting.

## The two roles

| | analyst | contractor |
|---|---|---|
| View the full project registry, map, and KPI summary | Yes | No (redirected to `/contractor`) |
| Open any project's detail page, run analysis, view risk breakdown | Yes | Yes, for their own projects (via "My Projects") |
| Export a PDF field report | Yes | N/A (not exposed in the contractor UI) |
| Register a new project (`POST /api/projects`) | No (403) | Yes — GPS coordinates mandatory |
| Upload before/after evidence (`POST /api/projects/{id}/evidence/upload`) | No | Yes, for a project they own (or that has no owner yet) and that has no coordinate |
| List "my projects" (`GET /api/projects/mine`) | No (403) | Yes |

There is no admin/superuser role, and no way to change a user's role after
registration through the API.

### What a contractor specifically cannot do

- Register a project *without* a GPS coordinate — the API rejects a create
  request missing `latitude`/`longitude` (they're required fields on
  `ProjectCreateIn`), and the frontend's registration form blocks submission
  client-side for the same reason before even calling the API.
- Upload evidence against a project that already has a coordinate — the
  endpoint explicitly returns 400 ("already has a GPS coordinate — it is
  screened automatically via satellite imagery").
- Upload evidence against a project owned by a *different* contractor
  account — 403 ("This project is owned by a different contractor
  account"). Uploading against an ownerless legacy project claims it for
  that contractor going forward.

## How role gating works

### Backend — `require_role`

`app/auth.py` defines a small dependency factory:

```python
def require_role(role: str):
    def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role != role:
            raise HTTPException(status_code=403, detail=f"This action requires the '{role}' role")
        return user
    return _dependency
```

Endpoints that need a specific role take it as a FastAPI dependency, e.g.
`current_user: User = Depends(require_role("contractor"))`
(`app/api/projects.py`'s `create_project`, `list_my_projects`,
`upload_manual_evidence`). This runs *before* the endpoint body — an
unauthorized request never reaches business logic. A missing/invalid token
is a separate 401 (raised by `get_current_user`/`_decode_token`), distinct
from a valid-but-wrong-role 403.

Read endpoints (`GET /api/projects`, `/{id}`, `/{id}/risk`, etc.) require
only `Depends(get_current_user)` — logged in as *either* role, no specific
role required — since a contractor also needs to browse the registry (e.g.
to find a no-coordinate project to attach evidence to). Only project
*creation* and *evidence upload* are further role-gated to contractor, and
only `/mine` additionally scopes results to the calling user.

### Frontend — `useRequireAuth`

`frontend/components/AuthProvider.tsx` exposes a `useRequireAuth(role?)`
hook used at the top of a protected page component
(`Dashboard.tsx` calls `useRequireAuth("analyst")`; `contractor/page.tsx`
calls `useRequireAuth("contractor")`):

```typescript
export function useRequireAuth(role?: "analyst" | "contractor") {
  const { user, loading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (loading) return;
    if (!user) { router.replace("/login"); return; }
    if (role && user.role !== role) {
      router.replace(user.role === "contractor" ? "/contractor" : "/");
    }
  }, [user, loading, role, router]);
  return { user, loading };
}
```

Behavior: no user at all → redirect to `/login`; wrong role → redirect to
that user's *own* correct dashboard (never a bare error page). This is a
UX convenience, not a security boundary by itself — the backend's
`require_role` dependency is what actually enforces access; a determined
client could call the API directly, which is exactly why the backend check
exists independently of the frontend redirect.

`AuthProvider` itself holds the current `user` in React context, persists
the JWT in `localStorage` (`lib/api.ts`'s `getToken`/`setToken`), and
attaches it as an `Authorization` header on every `fetchJson` call
automatically.

## Demo accounts (do not reuse in production)

Seeded automatically on first boot by `backend/scripts/seed_demo_users.py`,
idempotently (skipped if the email already exists):

| Role | Email | Password |
|---|---|---|
| analyst | `analyst@infrawatch.local` | `demo-analyst-2025` |
| contractor | `contractor@infrawatch.local` | `demo-contractor-2025` |

These exist purely so a fresh clone is immediately explorable without
registering first. Never reuse these credentials, or the default
`JWT_SECRET_KEY`, for anything reachable outside a developer's own machine.

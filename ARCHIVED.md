# ⚠️ REPOSITORY ARCHIVED — READ-ONLY

> **Notice:** As of **October 12, 2026**, this monorepo (`azmnexus/DWOP`) has been officially archived and placed into permanent read-only status following the successful execution of the approved Multi-Repository Migration Runbook (`docs/proposals/multi-repo-migration-roadmap.md`).
>
> **Do NOT commit code, open pull requests, or create branches in this repository.**

---

## 📌 Successor Repositories

Development has permanently migrated to three independent repositories under the **`azm-nexus-ai`** organization. All active feature work, bug fixes, and milestones (starting with Milestone O-05 Token Lifecycle) must be conducted exclusively in these repositories on the default branch `development`:

| Subsystem | New Repository | Primary Tech Stack | Extracted Paths & Scope |
|---|---|---|---|
| **Frontend** | [azm-nexus-ai/dwop-platform-web](https://github.com/azm-nexus-ai/dwop-platform-web) | Next.js 14, React 18, CSS Modules | Rooted Next.js web application (`frontend/` promoted to root) |
| **Backend & Contracts** | [azm-nexus-ai/dwop-platform-api](https://github.com/azm-nexus-ai/dwop-platform-api) | FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL | Rooted backend API (`backend/` promoted to root), `docs/`, `docs/contract/openapi.json` |
| **AI Microservices** | [azm-nexus-ai/dwop-ai-services](https://github.com/azm-nexus-ai/dwop-ai-services) | FastAPI, Celery, Redis | Event-driven AI asynchronous pipeline (Strict Invariant: zero direct DB writes) |

---

## 🏷️ Migration Baseline Tag

The exact final state of the monorepo prior to extraction is permanently preserved at:

- **Tag:** `pre-migration-baseline`
- **Commit:** `114f23b`
- **Branch:** `development`
- **Validation Status:** 14-suite regression sweep passing (14/14), Next.js build passing (13/13 routes), zero open PRs.

---

## 👥 Team Workstream Assignments

As per the migration cutover plan, team members are assigned as follows:

- **Usman (`mubus133`)** → `dwop-platform-web`
  - Rebase PR #12 RBAC enhancements into standalone web repo.
  - Implement Milestone O-05 token lifecycle frontend updates.
  - Author Milestone O-08 UAT pack.
- **Dotun (`LawdeWayde`)** → `dwop-platform-api` & `dwop-ai-services`
  - Implement Milestone O-07 audit wiring plan in `dwop-platform-api`.
  - Scaffold `dwop-ai-services` event consumer worker skeleton.
- **Khalifa (`kahmed-2101`)** → Async Senior Review
  - Multi-repo extraction audit and sign-off.
  - Review O-04 and O-06 drafts.
- **Engineering Lead** → Cross-Repo Coordination & Gate Governance
  - Migration verification, Gate 3 docs pack, CI oversight.

---

## ⏱️ 15-Minute Rollback Procedure (30-Day Buffer)

Per the migration proposal, a 30-day retention buffer is enforced. In the unlikely event that a catastrophic, unrecoverable blocker emerges across all three repositories during the initial cutover window:

1. **Unarchive Monorepo:** Org Administrator goes to `azmnexus/DWOP` -> **Settings** -> **Danger Zone** -> **Unarchive this repository**.
2. **Checkout Baseline:**
   ```bash
   git checkout pre-migration-baseline
   git checkout -b emergency-rollback-development
   ```
3. **Re-establish Remote Tracking:**
   ```bash
   git push -u origin emergency-rollback-development:development --force-with-lease
   ```
4. **Notify Team:** Announce rollback to engineering team, restore CI triggers, and pause downstream multi-repo pipelines.
5. **Post-Incident Review:** Convene architecture review before attempting re-extraction.

---

*Archived by Engineering Lead on October 12, 2026.*

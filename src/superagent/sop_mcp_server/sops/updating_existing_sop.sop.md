# SOP: Updating an existing SOP

## Purpose
Define the canonical steps for amending an existing SOP in the superagent's
SOP MCP server without breaking agents that already rely on the previous
wording, while preserving the auditability of SOP history.

## Preconditions
- You have identified the target SOP slug.
- You have read the current `<slug>.sop.md` end to end.
- You understand what is changing *and why* — the revision must be
  motivated by a concrete incident, feature change, or tooling change.

## Procedure

1. **Identify the slug.** Confirm the filename matches
   `src/superagent/sop_mcp_server/sops/<slug>.sop.md`. Do NOT rename;
   renaming breaks prompt lookup for any agent caching the prior slug.

2. **Classify the edit.** One of:
   - *Clarification*: wording change only, no behavior change.
   - *Correction*: the prior SOP had a mistake; behavior changes in
     small ways.
   - *Breaking*: the step sequence, required tool, or preconditions
     change materially.

3. **Preserve the top structure.** Do not reorder the canonical sections
   (Purpose, Preconditions, Procedure, Verification, Rollback,
   References). Add new sections only at the end and only after
   consultation.

4. **Make the edit.** Use the `editor` tool or an equivalent patch. Each
   edit should be a minimal diff that a reviewer can verify against the
   incident/feature motivating the change.

5. **Bump the revision footer.** Append (or update) a trailing section:
   ```
   ## Revision history
   - YYYY-MM-DD: <slug> — <one-line summary> (reason: <incident/feature>)
   ```
   Keep prior entries; newest on top.

6. **For Breaking edits only.** Add a `## Deprecations` block immediately
   above `## References` stating: the prior step number(s), the new
   equivalent, and the date after which the agent should prefer the new
   step. This lets downstream memory (`mem0_memory`) be invalidated
   explicitly.

7. **Validate locally.** Run `python -m superagent.sop_mcp_server --show
   <slug>` and diff against the previous committed version. Both the
   diff and the new full body must match the intended change.

8. **Invalidate caches.** If any agent persisted this SOP's body in
   `mem0_memory` (searchable by slug), delete those entries with
   `mem0_memory action="delete"` keyed by slug, or mark them stale with
   `metadata={"sop_revised": "<date>"}`.

## Verification
- `git diff HEAD~1 -- src/superagent/sop_mcp_server/sops/<slug>.sop.md`
  shows only the intended edit plus the revision footer (and the
  Deprecations block for Breaking edits).
- `python -m superagent.sop_mcp_server --show <slug>` returns the new
  body.
- A test invocation of the superagent on the SOP's canonical prompt
  produces the new expected behavior.

## Rollback
- `git revert` the commit containing the SOP edit. The revision footer
  block will revert with it; no further cleanup is needed.
- If `mem0_memory` entries were deleted in step 8, they will rebuild on
  the next relevant agent invocation — no explicit restore required.

## References
- Companion SOP for adding new entries: `adding_new_sop.sop.md`.
- MCP prompt lookup contract: agents MUST fetch the full body each
  session; never cache across releases.

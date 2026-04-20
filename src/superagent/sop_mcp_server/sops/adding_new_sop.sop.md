# SOP: Adding a new SOP to the superagent

## Purpose
Define the canonical steps for adding a new Standard Operating Procedure
(SOP) to the superagent's SOP MCP server so the agent can discover and
apply it through the same lookup pathway as every other SOP.

## Preconditions
- You have write access to the superagent repository.
- You know the concrete problem the SOP addresses (e.g. "ingesting a PDF",
  "responding to an on-call page", "migrating from tool X to tool Y").
- You have reviewed existing SOPs in
  `src/superagent/sop_mcp_server/sops/` to avoid duplication.

## Procedure

1. **Choose a slug.** Pick a lowercase snake_case slug that captures the
   SOP's intent (e.g. `handling_rate_limits`). The filename MUST be
   `<slug>.sop.md`. The double extension lets the MCP server detect SOP
   documents without ambiguity.

2. **Draft the file.** Create `src/superagent/sop_mcp_server/sops/<slug>.sop.md`
   with the following top-level sections, in order:
   - `# SOP: <Short Title>` (H1, human readable)
   - `## Purpose` (one paragraph: why this SOP exists)
   - `## Preconditions` (bullets: what must be true before running the SOP)
   - `## Procedure` (numbered steps; each step starts with an imperative
     verb and names the tool or surface involved)
   - `## Verification` (bullets: how to confirm success)
   - `## Rollback` (bullets: how to undo if a step fails midway)
   - `## References` (bullets: source-of-truth links, commit hashes, or
     ticket IDs)

3. **Name tools explicitly.** When a step requires a specific tool, spell it
   out: `editor`, `shell`, `mcp_client`, `swarm`, `graph`, `workflow`,
   `use_agent`, `batch`, `mem0_memory`, `code_interpreter`, `ubuntu_desktop`,
   `load_tool`, `a2a_client`. Do not paraphrase ("run a command" → use
   `shell`).

4. **Keep it deterministic.** Every step must be reproducible. Replace
   "check the logs" with exact commands, file paths, or search strings.
   Replace subjective language ("look carefully") with concrete criteria.

5. **Register implicitly.** The SOP MCP server (`superagent.sop_mcp_server`)
   globs `*.sop.md` at startup — no manifest edit is required. The SOP's
   slug becomes its MCP prompt name.

6. **Validate locally.** Run `python -m superagent.sop_mcp_server --list`
   (stdio server's list mode). The new slug must appear, with its Purpose
   paragraph as the description.

7. **Update the index.** If `src/superagent/sop_mcp_server/sops/INDEX.md`
   exists, append a one-line entry: `- <slug>: <one-line summary>`.

## Verification
- `python -m superagent.sop_mcp_server --list` shows the new slug.
- The superagent, when handed a prompt that matches the SOP's Purpose,
  calls `mcp_client` with `prompt=<slug>` and receives the full body.
- A fresh clone of the repo followed by the commands above produces
  identical output (no uncommitted dependencies).

## Rollback
- Remove the file `src/superagent/sop_mcp_server/sops/<slug>.sop.md`.
- Revert the `INDEX.md` entry if one was added.
- Re-run the list command and confirm the slug is gone.

## References
- MCP prompts spec: https://modelcontextprotocol.io/specification/
- The companion SOP for editing existing entries: `updating_existing_sop.sop.md`.

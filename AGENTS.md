# Project working instructions

- Read `project.md` at the start of every chat/task before making changes. Consult `README.md` and referenced design notes as needed.
- Update `project.md` after every project change, including code, configuration, documentation, tests, or research-design changes. Before finishing a task, record what changed, verification actually performed, current limitations, and next steps. Keep it concise and current; never claim an unrun check passed.
- Use a Git branch named for the current task, in lowercase hyphen-separated words (for example `add-transformation-tests`). Do not use `codex/` or another automatic prefix. Reuse the branch when continuing the same task; create a new task-named branch for a new task. Respect an exact branch name supplied by the user.
- Inspect Git status before changing branches. Preserve existing uncommitted work; do not reset, discard, or overwrite it to enforce branch naming.
- Maintain the offline pilot: no credentials, paid services, GPU, or model downloads for its default execution path.
- Keep benchmark truth and oracle outputs outside worker/model inputs. Preserve acquisition ancestry across copies and routing. Unknown lineage must not become independent support.
- Mock outputs are software diagnostics, never empirical LLM findings. Do not scale to the full benchmark or add real-model experiments until the user requests that next phase.

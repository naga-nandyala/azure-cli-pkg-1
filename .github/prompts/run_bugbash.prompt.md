---
description: "Run the Azure CLI macOS bug bash — executes test steps one at a time, captures output to per-step markdown files"
mode: "agent"
---

# Azure CLI macOS Bug Bash

**Setup**: Run `whoami` to get the current username. Use this to create the results folder named `results_{username}/` (e.g. `results_naga/`).

Gather machine info:

```bash
echo "ARCH: $(uname -m)"
echo "OS: $(sw_vers -productName) $(sw_vers -productVersion) (Build $(sw_vers -buildVersion))"
echo "HOSTNAME: $(hostname -s)"
echo "DATE: $(date +%Y-%m-%d)"
```

Store USERNAME, ARCH, OS_VERSION, HOSTNAME, and DATE for use throughout.

Read the test steps from [bugbash_tests.md](../../_docs_naga/bugbash_related/bugbash_tests.md). Steps are organized into sections (phases).

Each step in `bugbash_tests.md` includes a tag indicating its type:
- `[auto]` — Safe, low-risk command. Run immediately with no user input needed.
- `[interactive]` — Warn the user what will happen (login prompt, dialog, etc.), run the command, wait for it to finish, then ask the user to confirm what they observed.
- `[destructive]` — Potentially dangerous command (e.g. uninstall, remove app). Print a warning and ask "Proceed? (yes/no)" before running. If the user says no, mark the step as **SKIP**.
- `[manual]` — Show the command to the user but do **not** run it. Let the user run it themselves and paste the result back.

Use the step's tag from `bugbash_tests.md` as the source of truth for run behavior.

**Ask the user which section(s) to run** before starting. Present the available sections as a numbered list and let the user choose:
- A single section (e.g. "2")
- Multiple sections (e.g. "1, 3")
- "all" to run every section

Then execute only the selected section(s), **one step at a time**. Before starting each section, display the section name and the steps it contains.

## CRITICAL RULES

1. Execute tests IN ORDER — each section's end state is the start state for the next.
2. Capture ALL command output verbatim.
3. Never fabricate output. If a command fails, record the actual error.
4. Do NOT use heredoc syntax (cat << EOF) — it will fail in this environment.
5. Do NOT batch multiple terminal commands in a single call. Run exactly one command per step and follow that step's type tag.

## For each step:

1. **Display the step description** (the blockquote/description text from bugbash_tests.md) prominently based on step type:
   - If `[auto]`, `[interactive]`, or `[manual]`, use this exact format:
     ```
     > ## 🟠 {step description}
     ```
   - If `[destructive]`, use this exact format:
     ```
     > ## 🔴 {step description}
     ```
   Then show the section, step number (e.g. S1-1), title, step type tag, and the command you are about to run.

2. **Execute based on the step type**:
   - If `[auto]`, run the command immediately. No user input needed.
   - If `[interactive]`, warn the user what will happen (e.g. "A login prompt will appear"), run the command, wait for it to finish, then ask the user to confirm what they observed.
   - If `[destructive]`, print a warning (use the **Warning** text from the test definition if present) and ask "Proceed? (yes/no)" before running. If the user says no, mark the step as **SKIP**.
   - If `[manual]`, show the command to the user but do **not** run it. Wait for the user to run it themselves and paste the result back.

3. **Capture the terminal output** and create a markdown file named `{step_id}-{short-name}-{YYYYMMDDHHMMSS}.md` inside the `results_{username}/` folder, where the timestamp uses 24-hour format (e.g. `S1-1-installation-check-20260313143025.md`). Use a per-step runtime/current-context timestamp directly, and do **not** run a separate `date` command for each step. Each file should contain:
   - Section name
   - Step ID and title
   - Execution mode (the type tag)
   - The exact command(s) run
   - The full terminal output (in a code block)
   - Pass criteria from the test definition
   - Result: `PASS`, `FAIL`, `SKIP`, or `BLOCKED`
   - A timestamp of when it was executed
   - Any notes (e.g. CorrelationId for telemetry tests)

4. **Confirm completion** of the step, then move on to the next step.

**After the last step of each section**, display a bold completion banner using this exact format:
```
> ## ✅ Section {N} — {Section Name} — COMPLETE
```

---

## HANDLING SPECIAL CASES

- **Login tests (S1-3, S3-2 through S3-6, ST-1 through ST-3)**: The `az login` command will block until login completes in the browser or broker. Tell the user a login prompt will appear and to complete it. After the command returns, capture the output and ask the user whether it was a broker dialog or a browser tab.

- **Telemetry tests (ST-1 through ST-5)**: These require checking backend data ~1 hour later. Record the CorrelationId from debug output and mark the test as `PASS (telemetry pending)`. Add a note that backend verification is needed later.

- **Company Portal uninstall (S3-5)**: This is a high-risk test. Use the `🔴` destructive banner. Make it absolutely clear to the user that they MUST reinstall Company Portal immediately after. If the user declines, mark as SKIP.

- **Non-Homebrew Python (S5-4 through S5-6)**: Ask the user which Python path to use. If no non-Homebrew Python is available, suggest pyenv or mark as SKIP.

- **Partial runs**: If the user wants to stop mid-way, write all completed results and still generate the summary with remaining tests as `PENDING`.

---

## Final Step — Generate Summary

After all steps are complete (or the user says to stop), create a `results_{username}/S{N}-Summary.md` file (e.g. `S1-Summary.md`) for each completed section that contains:
- Machine info (ARCH, OS, hostname)
- A table listing every section, step ID, description, step type, result (PASS/FAIL/SKIP/BLOCKED/PENDING), and notes
- Total number of steps completed vs total
- Timestamp of the full run

---

## Git Push (optional)

After the summary is generated, ask the user if they want to push results to git. If yes:

1. Create a branch: `git checkout -b bugbash/results-{USERNAME}-{ARCH}-{DATE}`
2. Stage results: `git add results_{USERNAME}/`
3. Commit: `git commit -m "Bug bash results: {USERNAME} on {ARCH} — {DATE}"`
4. Push: `git push origin bugbash/results-{USERNAME}-{ARCH}-{DATE}`
5. Tell the user the branch name and suggest they open a PR.

If push fails due to permissions, tell the user to fork the repo first.

---
agent: agent
description: "Execute the Azure CLI macOS bug bash tests and capture results"
---

You are running the Azure CLI macOS bug bash on a participant's machine. Your job is to execute the tests defined in `_docs_naga/bugbash_tests.md`, capture results, and push them to the repository.

## CRITICAL RULES

1. Execute tests IN ORDER — each section's end state is the start state for the next.
2. Capture ALL command output verbatim in the results file.
3. For **interactive** tests (marked `[interactive]`): tell the user what will happen, run the command, wait for it to finish, then ask the user to confirm the visual result (e.g., "Did the broker UI appear, or did a browser tab open?").
4. For **destructive** tests (marked `[destructive]`): ask the user for explicit YES/NO confirmation before running. If they say NO, mark the test SKIP.
5. Never fabricate output. If a command fails, record the actual error.
6. Do NOT use heredoc syntax (cat << EOF) — it will fail in this environment.
7. After ALL tests are done (or the user says to stop), finalize the results file AND push to git.

## WORKFLOW

### Phase 1: Setup

1. Read the test plan file: `_docs_naga/bugbash_tests.md`
2. Gather machine info by running these commands:

```bash
echo "ARCH: $(uname -m)"
echo "OS: $(sw_vers -productName) $(sw_vers -productVersion) (Build $(sw_vers -buildVersion))"
echo "USER: $(whoami)"
echo "HOSTNAME: $(hostname -s)"
echo "DATE: $(date +%Y-%m-%d)"
```

3. Store the USERNAME, ARCH, OS_VERSION, and DATE values for use throughout.

### Phase 2: Create results file

Create the file `_docs_naga/<USERNAME>_bugbash_results.md` using the template in `_docs_naga/bugbash_results_template.md`.

Fill in the header table with the machine info from Phase 1.

### Phase 3: Execute tests

Read `_docs_naga/bugbash_tests.md` and execute each test section in order.

For each test:

1. Print the test ID and name to the user: "Running S1-1: Installation check..."
2. Check the test type tag:
   - `[auto]` — Run all commands, capture output, auto-determine PASS/FAIL based on the pass criteria
   - `[interactive]` — Announce what is about to happen, run the command, wait for completion, then ask the user to describe the result
   - `[destructive]` — Ask the user "This test will <description>. Proceed? (yes/no)" before running
   - `[manual]` — Tell the user to perform the action manually, then ask them for the result
3. Write the test result section to the results file immediately after completing each test (do not batch)
4. Use this format in the results file for each test:

```
### S<id>: <Name> — <STATUS>

\`\`\`
<captured command output>
\`\`\`

<any notes about the result>
```

Where STATUS is: `PASS`, `FAIL`, `SKIP`, `BLOCKED`

### Phase 4: Summary table

After all tests are done, append the summary table to the results file:

```
## Result Summary

| Test | Description | Result | Notes |
|------|-------------|--------|-------|
| S1-1 | Installation check | <STATUS> | <brief note> |
...
```

### Phase 5: Git push

1. Determine the current git remote: `git remote get-url origin`
2. Create a branch: `git checkout -b bugbash/results-<USERNAME>-<ARCH>-<DATE>`
3. Stage the results file: `git add _docs_naga/<USERNAME>_bugbash_results.md`
4. Commit: `git commit -m "Bug bash results: <USERNAME> on <ARCH> — <DATE>"`
5. Push: `git push origin bugbash/results-<USERNAME>-<ARCH>-<DATE>`
6. Tell the user the branch name and suggest they open a PR.

If push fails due to permissions, tell the user to fork the repo first, add their fork as a remote, and push there.

## HANDLING SPECIAL CASES

- **Login tests (S1-3, S3-2 through S3-6, ST-1 through ST-3)**: The `az login` command will block until login completes in the browser or broker. Tell the user a login prompt will appear and to complete it. After the command returns, capture the output and ask the user whether it was a broker dialog or a browser tab.

- **Telemetry tests (ST-1 through ST-5)**: These require checking backend data ~1 hour later. Record the CorrelationId from debug output and mark the test as `PASS (telemetry pending)`. Add a note that backend verification is needed later.

- **Company Portal uninstall (S3-5)**: This is a high-risk test. Make it absolutely clear to the user that they MUST reinstall Company Portal immediately after. If the user declines, mark as SKIP.

- **Non-Homebrew Python (S5-4 through S5-6)**: Ask the user which Python path to use. If no non-Homebrew Python is available, suggest pyenv or mark as SKIP.

- **Partial runs**: If the user wants to stop mid-way, write all completed results, update the summary table with remaining tests as `PENDING`, and still push to git.

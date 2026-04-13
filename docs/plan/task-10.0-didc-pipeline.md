The key remaining prerequisites are:

1. Confirm deploy target contract
- Decide whether CD deploys by artifact handoff or direct git pull on the runner.
- Decide release layout on server: current symlink pattern vs in-place overwrite.

2. Confirm local hosted runner details
- Runner labels, OS user, working directory, and service account permissions.
- Access needed for restart commands and deployment paths.

3. Lock runtime operating model for conversion jobs
- For task-10.2-conversion-workflow.md: pick first implementation mode:
  - watched folder only, or
  - queue + worker (SQLite/Redis), or
  - manual enqueue CLI.
- This choice affects runbook and CD restart behavior.

4. Define secrets and environment inventory
- Required repo/environment secrets for CI/CD.
- Required runtime env vars for conversion service/worker.
- Keep names and ownership documented before writing workflows.

5. Define rollback and smoke-check gates
- One rollback command/path.
- One post-deploy smoke conversion command and pass criteria.

6. Sync task docs one more time
- task-10.1-ci-cd-pipeline.md
- task-10.2-conversion-workflow.md
- Ensure acceptance criteria are testable and unambiguous.

If you want, I can do this immediately as the next step:
1. Add a concise pre-implementation decision checklist doc.
2. Then scaffold initial CI/CD workflow files with placeholders only where decisions are still pending.
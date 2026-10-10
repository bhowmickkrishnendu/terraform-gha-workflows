# Reusable Terraform GitHub Actions workflows

This repository provides reusable plan, apply, and destroy workflows. Pin callers to the full commit SHA of the published `v3.0.0` release, with a version comment. Published version tags must not be moved. Every caller supplies the AWS Region, OIDC role ARN, component name, and Terraform root path. The optional `root_directory` input falls back to `environments/<environment>/<component>` for older callers.

The plan job checks formatting, initializes with the committed provider lock file, validates the root, and saves a binary plan. It returns `has_changes` and `plan_sha256`. A changed plan is uploaded for one day unless `upload_plan: false` is passed for a manual read-only plan. The logs show Terraform's readable plan, including diagnostics, attribute changes, and output changes. The job summary renders the saved plan before approval. Current state outputs appear in logs and the summary even when there are no changes; these are values before apply, not proposed values. A no-change plan explicitly explains that apply will skip. Sensitive values marked in Terraform remain redacted in human-readable output. Saved plans can contain secrets, so restrict Actions access and do not download or publish them casually.

The apply job must receive `expected_plan_sha256` and `approval_environment`. It waits at that GitHub environment, checks that required reviewers are configured, verifies the saved plan digest, and applies the exact plan from the same workflow run. It then prints the applied state outputs in logs and the summary. The caller must put plan and apply in dependent jobs and pass the plan outputs. Create a separate protected environment for each stack. An environment name alone is not an approval rule.

Destroy is a separate manual path. It requires the exact text `DESTROY`, creates a destroy plan, waits at its protected environment when changes exist, verifies the plan digest, and applies that saved destroy plan. Pass the same root, Region, and variable filename to plan, apply, and destroy. The caller should also serialize live workflows so two runs do not compete for the same state.

This repository does not create IAM roles, GitHub environments, or branch protection rules. The caller owns those settings and should use a separate PR validation workflow that never exposes a live state role to untrusted PR code.

## v3.0.0 migration and artifact security

Apply and destroy now require the `TF_PLAN_PASSPHRASE` secret. Plans also require it when uploading changed plans; `upload_plan: false` does not need it. Generate at least 32 random characters (`openssl rand -hex 32`), save the value as a repository Actions secret in the caller, and explicitly pass only that secret to each plan/apply/destroy reusable job:

```yaml
secrets:
  TF_PLAN_PASSPHRASE: ${{ secrets.TF_PLAN_PASSPHRASE }}
```

Artifacts contain only encrypted plans: AES-256-CBC with a random salt and PBKDF2-SHA256 (200,000 iterations). Apply decrypts and verifies the original SHA256 against the trusted plan output before Terraform reads the plan. Digest verification is mandatory for integrity; CBC alone does not authenticate ciphertext. Human-readable Terraform redaction is preserved, but unmarked secrets in Terraform configuration can still appear in logs. No plaintext plan is uploaded. A missing or short key fails safely.

Artifact names include the run attempt. Always use **Re-run all jobs**, so plans, approvals, and artifacts belong to the same attempt. Retention remains one day. Expired artifacts need a new full run. Never print the passphrase; rotate it after pending deployments finish, then rerun all jobs. v2 artifacts cannot be used by v3 apply.

## Execution and approval controls

Live workflows accept only push, manual, or scheduled events on the caller's default branch. PR events, feature branches, and tags fail before AWS credentials. Root and variable paths must resolve inside the workspace, and provider lock files are mandatory. Shell inputs are passed as quoted environment variables; checkout does not persist tokens. Actions are pinned to verified commit SHAs, with weekly Dependabot updates.

Apply and destroy retain reviewer checks, latest-commit verification, and exact-plan checks. State locks wait up to five minutes; running jobs time out after 60 minutes. Pending approval time is separate from execution timeout. Callers must serialize all live workflows with a shared concurrency group and cancellation disabled. For separation of duties, configure independent reviewers, prevent self-review, disable admin bypass, and restrict deployments to the default branch. Use separate restricted plan and deployment OIDC roles where possible; this release does not change IAM or repository settings.

Use explicit status functions on downstream jobs to avoid GitHub's implicit `success()` skipping valid deployments after no-change upstream applies:

```yaml
if: ${{ !cancelled() && needs.compute_plan.result == 'success' && needs.compute_plan.outputs.has_changes == 'true' }}
```

Callers should include a final deployment gate that fails if any changed plan was not applied. Plan and apply must use matching root, Terraform version, Region, environment, and component. A stale branch revision fails before apply; Terraform also rejects saved plans after intervening state changes.

## Validation and release process

`Shared workflow checks` runs on PRs, pushes to main, and merge queues without AWS credentials. It runs checksum-verified actionlint and regression tests against workflow shell scripts: changed/no-change/error plans, shell injection, encryption round-trip, wrong keys, digest mismatch, and rejected PR events. Run `python .github/tests/test_workflows.py` locally with PyYAML installed (Windows needs Git Bash).

Merge only after CI passes, publish a new version from the merge commit, and update caller SHAs in a separate PR. Tests verify local workflow behavior; live AWS permissions and approval settings require a reviewed deployment through the protected environments.

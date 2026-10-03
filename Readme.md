# Reusable Terraform GitHub Actions workflows

This repository provides reusable plan, apply, and destroy workflows. Callers must pin a reviewed commit SHA. Every caller supplies the AWS Region, OIDC role ARN, component name, and Terraform root path. The optional `root_directory` input falls back to `environments/<environment>/<component>` for older callers.

The plan job checks formatting, initializes with the committed provider lock file, validates the root, and saves a binary plan. It returns `has_changes` and `plan_sha256`. A changed plan is uploaded for one day unless `upload_plan: false` is passed for a manual read-only plan. The job summary lists only resource addresses and actions. Saved plans can contain secrets, so restrict Actions access and do not download or publish them casually.

The apply job must receive `expected_plan_sha256` and `approval_environment`. It waits at that GitHub environment, checks that required reviewers are configured, verifies the saved plan digest, and applies the exact plan from the same workflow run. The caller must put plan and apply in dependent jobs and pass the plan outputs. Create a separate protected environment for each stack. An environment name alone is not an approval rule.

Destroy is a separate manual path. It requires the exact text `DESTROY`, creates a destroy plan, waits at its protected environment when changes exist, verifies the plan digest, and applies that saved destroy plan. Pass the same root, Region, and variable filename to plan, apply, and destroy. The caller should also serialize live workflows so two runs do not compete for the same state.

This repository does not create IAM roles, GitHub environments, or branch protection rules. The caller owns those settings and should use a separate PR validation workflow that never exposes a live state role to untrusted PR code.

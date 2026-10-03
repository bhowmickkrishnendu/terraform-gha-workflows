# Reusable Terraform GitHub Actions workflows

This repository provides reusable plan, apply, and destroy workflows under `.github/workflows/`. A caller supplies its AWS region, GitHub OIDC role ARN, environment name, and component name. The plan and apply workflows share a plan artifact named with the environment and component.

## Terraform root path

The optional `root_directory` input points to the Terraform root in the caller repository. For a repository with `stacks/networking`, pass `root_directory: stacks/networking`. Plan, apply, and destroy must receive the same path for that component. The value is relative to the caller repository root.

If `root_directory` is omitted, the workflows continue to use `environments/<environment>/<component>`. This keeps existing callers working while they update their folder layouts.

```yaml
jobs:
  plan:
    uses: OWNER/terraform-gha-workflows/.github/workflows/terraform-plan.yml@PINNED_COMMIT
    with:
      environment: dev
      component: networking
      root_directory: stacks/networking
      aws_region: YOUR_REGION
      terraform_version: 1.14.2
      tfvars_file: dev.tfvars
      role_to_assume: ${{ vars.AWS_TERRAFORM_ROLE_ARN }}
    secrets:
      INFRACOST_API_KEY: ${{ secrets.INFRACOST_API_KEY }}
```

Pin a reviewed commit in callers. The workflows use GitHub OIDC to assume the supplied AWS role. They do not need AWS access keys in repository secrets. Check the caller's plan, approval, and artifact settings before enabling apply or destroy.

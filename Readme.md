# 🚀 Terraform GHA Workflows

This repository provides **modular, reusable GitHub Actions workflows** designed for automating **Terraform CI/CD pipelines** in a clean, DRY, and enterprise-ready manner.

## 📦 Included Shared Workflows

These workflows are stored in `.github/workflows/shared/` and intended to be **reused via `workflow_call`** from other Terraform repositories:

| Workflow       | Description                          |
|----------------|--------------------------------------|
| `init.yml`     | Runs `terraform init`                |
| `validate.yml` | Runs `terraform validate`            |
| `plan.yml`     | Runs `terraform plan` and stores output for review |
| `apply.yml`    | Runs `terraform apply` using saved plan |
| `destroy.yml`  | Runs `terraform destroy`             |

## 📘 Example Usage

To use from another repo (e.g. `AWS-With-Terraform`):

```yaml
jobs:
  plan:
    uses: bhowmickkrishnendu/terraform-gha-workflows/.github/workflows/shared/plan.yml@v1.0.0
    with:
      working-directory: path/to/terraform/module
```

Make sure to create a **tag (e.g. `v1.0.0`)** and reference it using `@v1.0.0`.

## ✅ Requirements

- Terraform v1.6 or higher
- GitHub Actions enabled
- AWS credentials provided via secrets

## 🔐 Required Secrets

Add these secrets to your repo that is using the shared workflows:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

## 🏗 Recommended Directory Layout in Repos Using This

```
.
└── .github/
    └── workflows/
        └── uat.yml     # Calls shared workflows from this repo
```

## 📌 Maintainer

**Author:** [Krishnendu Bhowmick](https://github.com/bhowmickkrishnendu)  
Feel free to fork or raise issues for improvement.

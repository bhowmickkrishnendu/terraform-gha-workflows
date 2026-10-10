"""Run workflow policy checks and real bash/OpenSSL tests without AWS credentials."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which('bash')
if os.name == 'nt':
    BASH = 'C:/Program Files/Git/bin/bash.exe'


def shell_path(path):
    value = Path(path).resolve().as_posix()
    return '/' + value[0].lower() + value[2:] if os.name == 'nt' else value


def load(name):
    return yaml.load((ROOT / '.github/workflows' / name).read_text(), Loader=yaml.BaseLoader)


def step(workflow, job, name):
    return next(item for item in workflow['jobs'][job]['steps'] if item['name'] == name)


def run_script(script, root, environment):
    env = dict(os.environ, **environment)
    return subprocess.run([BASH, '-e', '-o', 'pipefail', '-c', script], cwd=root, env=env, capture_output=True, text=True)


class WorkflowTests(unittest.TestCase):
    def test_privileged_workflow_policy(self):
        for name in ('terraform-plan.yml', 'terraform-apply.yml', 'terraform-destroy.yml'):
            workflow = load(name)
            for job in workflow['jobs'].values():
                self.assertIn('timeout-minutes', job)
                self.assertEqual(job['permissions']['contents'], 'read')
                names = [s['name'] for s in job['steps']]
                self.assertLess(names.index('Require a trusted branch event'), names.index('Configure AWS credentials'))
                self.assertLess(names.index('Validate Terraform root and inputs'), names.index('Configure AWS credentials'))
                for item in job['steps']:
                    if 'uses' in item:
                        self.assertRegex(item['uses'], r'@[a-f0-9]{40}$')
                    if 'run' in item:
                        self.assertNotIn('${{', item['run'])
                        self.assertNotIn('-lock=false', item['run'])
                    if item.get('uses', '').startswith('actions/checkout@'):
                        self.assertEqual(item['with']['persist-credentials'], 'false')
                    if item.get('uses', '').startswith('actions/upload-artifact@'):
                        self.assertTrue(item['with']['path'].endswith('.enc'))
                        self.assertEqual(item['with']['retention-days'], '1')
                if 'Decrypt saved plan' in names:
                    digest = next(n for n in names if n.startswith('Verify ') and 'digest' in n)
                    apply = next(n for n in names if n.startswith('Apply '))
                    self.assertLess(names.index('Decrypt saved plan'), names.index(digest))
                    self.assertLess(names.index(digest), names.index(apply))
                    self.assertLess(names.index('Require configured reviewers for this stack'), names.index('Configure AWS credentials'))

    def test_plan_exit_codes_and_shell_input(self):
        for name, job, title in (
            ('terraform-plan.yml', 'terraform', 'Save and summarize plan'),
            ('terraform-destroy.yml', 'destroy-plan', 'Save destroy plan'),
        ):
            script = step(load(name), job, title)['run']
            for exit_code in (0, 2, 1):
                with self.subTest(workflow=name, exit_code=exit_code), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    binary = root / 'bin'
                    binary.mkdir()
                    stub = binary / 'terraform'
                    stub.write_text('''#!/bin/bash
case "$1" in
  plan)
    for arg in "$@"; do
      case "$arg" in -out=*) printf 'saved-plan' > "${arg#-out=}" ;; esac
    done
    printf 'plan output\n'
    exit "$MOCK_EXIT" ;;
  show) printf 'redacted plan\n' ;;
  *) exit 1 ;;
esac
''', newline='\n')
                    stub.chmod(0o755)
                    outputs = root / 'outputs'
                    summary = root / 'summary'
                    env = {
                        'MOCK_BIN': shell_path(binary), 'MOCK_EXIT': str(exit_code),
                        'GITHUB_OUTPUT': shell_path(outputs), 'GITHUB_STEP_SUMMARY': shell_path(summary),
                        'RUNNER_TEMP': shell_path(root), 'GITHUB_SHA': 'a' * 40, 'TF_COMPONENT': 'compute',
                        'TFVARS_FILE': '$(touch injected).tfvars',
                    }
                    result = run_script('export PATH="$MOCK_BIN:$PATH"\n' + script, root, env)
                    self.assertEqual(result.returncode, 1 if exit_code == 1 else 0, result.stderr)
                    self.assertFalse((root / 'injected').exists())
                    if exit_code != 1:
                        self.assertIn('has_changes=' + ('true' if exit_code == 2 else 'false'), outputs.read_text())
                        self.assertIn(hashlib.sha256(b'saved-plan').hexdigest(), outputs.read_text())
                    else:
                        self.assertFalse(outputs.exists())

    def test_artifact_encryption_and_integrity(self):
        plan = load('terraform-plan.yml')
        apply = load('terraform-apply.yml')
        encrypt = step(plan, 'terraform', 'Encrypt sensitive plan')['run']
        decrypt = step(apply, 'terraform-apply', 'Decrypt saved plan')['run']
        verify = step(apply, 'terraform-apply', 'Verify saved plan digest')['run']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = b'private-key-test-fixture\n'
            (root / 'tfplan').write_bytes(payload)
            env = {'TF_PLAN_PASSPHRASE': 'test-only-' + 'a' * 64, 'EXPECTED_PLAN_SHA256': hashlib.sha256(payload).hexdigest()}
            self.assertEqual(run_script(encrypt, root, env).returncode, 0)
            self.assertNotIn(payload.strip(), (root / 'tfplan.enc').read_bytes())
            (root / 'tfplan').unlink()
            self.assertEqual(run_script(decrypt, root, env).returncode, 0)
            self.assertEqual(run_script(verify, root, env).returncode, 0)
            (root / 'tfplan').write_bytes(b'tampered')
            self.assertNotEqual(run_script(verify, root, env).returncode, 0)
            self.assertNotEqual(run_script(decrypt, root, dict(env, TF_PLAN_PASSPHRASE='wrong-' + 'b' * 64)).returncode, 0)
            self.assertNotEqual(run_script(encrypt, root, dict(env, TF_PLAN_PASSPHRASE='')).returncode, 0)

    def test_untrusted_events_rejected(self):
        script = step(load('terraform-plan.yml'), 'terraform', 'Require a trusted branch event')['run']
        with tempfile.TemporaryDirectory() as directory:
            for event in ('pull_request', 'pull_request_target', 'merge_group'):
                self.assertNotEqual(run_script(script, directory, {'CALLER_EVENT': event, 'CALLER_REF': 'refs/heads/master', 'DEFAULT_BRANCH': 'master'}).returncode, 0)
            self.assertEqual(run_script(script, directory, {'CALLER_EVENT': 'push', 'CALLER_REF': 'refs/heads/master', 'DEFAULT_BRANCH': 'master'}).returncode, 0)
            self.assertNotEqual(run_script(script, directory, {'CALLER_EVENT': 'push', 'CALLER_REF': 'refs/tags/v1', 'DEFAULT_BRANCH': 'master'}).returncode, 0)
            self.assertNotEqual(run_script(script, directory, {'CALLER_EVENT': 'workflow_dispatch', 'CALLER_REF': 'refs/heads/feature', 'DEFAULT_BRANCH': 'master'}).returncode, 0)

    def test_paths_cannot_escape_workspace(self):
        script = step(load('terraform-plan.yml'), 'terraform', 'Validate Terraform root and inputs')['run']
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            workspace = base / 'workspace'
            root = workspace / 'compute'
            root.mkdir(parents=True)
            (root / '.terraform.lock.hcl').touch()
            (root / 'terraform.tfvars').touch()
            (base / 'outside.tfvars').touch()
            env = {'GITHUB_WORKSPACE': shell_path(workspace), 'TF_ROOT': shell_path(root), 'TF_COMPONENT': 'compute', 'TFVARS_FILE': 'terraform.tfvars'}
            self.assertEqual(run_script(script, workspace, env).returncode, 0)
            self.assertNotEqual(run_script(script, workspace, dict(env, TFVARS_FILE='../../outside.tfvars')).returncode, 0)
            self.assertNotEqual(run_script(script, workspace, dict(env, TF_ROOT=shell_path(base))).returncode, 0)
            self.assertNotEqual(run_script(script, workspace, dict(env, TF_COMPONENT='compute/../../elsewhere')).returncode, 0)


if __name__ == '__main__':
    unittest.main()

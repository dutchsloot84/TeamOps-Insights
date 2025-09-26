# Git Historian Pull Request Runbook

This runbook documents how to unblock the Weekly Git Historian workflow when it needs to push commits and open pull requests using the built-in `GITHUB_TOKEN`.

## 1. One-time repository settings change

1. Navigate to **Settings → Actions → General** in the GitHub repository UI.
2. Under **Workflow permissions**, select **Read and write permissions**.
3. Check **Allow GitHub Actions to create and approve pull requests**.
4. Click **Save**.

These settings ensure the token provided to the workflow has the correct scopes to create branches and open pull requests.

## 2. Workflow configuration

The workflow must declare the permissions it requires. The Weekly Git Historian workflow already includes:

```yaml
permissions:
  contents: write
  pull-requests: write
```

If you add new jobs that also need to write to the repository or PRs, ensure they either inherit these defaults or request the scopes explicitly.

## 3. Verification

After updating the repository settings, run the workflow manually:

1. Go to **Actions → Weekly Git Historian**.
2. Click **Run workflow** and keep the default inputs.
3. Confirm that a branch named `auto/history-<date>` is created and that a pull request is opened by the bot account.

If the workflow still fails with permission errors, re-check the settings above or consider using a PAT stored in `secrets.ACTIONS_BOT_TOKEN` temporarily.

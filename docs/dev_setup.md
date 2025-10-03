# Developer setup notes

## AWS CDK

The CDK app is configured via the repository root `cdk.json`. From the repository root you can run:

```bash
npm run cdk:venv
npm run cdk:list
npm run cdk:synth
npm run cdk:diff
npm run cdk:deploy
```

These commands rely on CDK's default auto-discovery, so no additional `-a` flags or wrapper scripts are required. Run `npm run cdk:venv` whenever dependencies change to refresh the virtual environment. Ensure Python 3.11 and Node.js 20 are installed locally so the CLI matches the GitHub Actions environment.

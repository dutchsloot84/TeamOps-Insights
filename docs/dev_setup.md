# Developer setup notes

## AWS CDK

The CDK app is configured via the repository root `cdk.json`. From the repository root you can run:

```bash
npm run cdk:list
npm run cdk:synth
npm run cdk:deploy:all
```

These commands rely on CDK's default auto-discovery, so no additional `-a` flags or wrapper scripts are required. Ensure Python 3.11 and Node.js 20 are installed locally so the CLI matches the GitHub Actions environment.

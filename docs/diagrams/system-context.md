# System Context

```mermaid
flowchart LR
  User([Engineer / RM / DevOps]) -->|Run audit, view reports| UI[Web UI (Streamlit)]
  User -->|CLI usage| CLI[CLI Tool]

  subgraph ReleaseCopilot-AI
    CLI --> Core[Audit Core]
    UI --> Core
    Core --> Jira[Jira Client (OAuth 3LO)]
    Core --> BB[Bitbucket Client]
    Core --> Match[Story↔Commit Matcher]
    Core --> Export[Exporter (Excel/JSON)]
    Core --> Agents[Agents (LangGraph/crewAI)]
    Agents --> MCP[MCP Memory Layer]
  end

  subgraph AWS
    Core --> S3[(S3 Reports/Artifacts)]
    Core --> Secrets[Secrets Manager]
    Depl[Lambda/ECS Task] --> Core
  end

  Jira <--> |REST v3| JiraCloud[(Jira Cloud)]
  BB <--> |REST| BitbucketCloud[(Bitbucket Cloud)]

  Export --> |Download| UI
  S3 --> |Download links| UI
```

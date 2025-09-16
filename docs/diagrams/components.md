# Components

```mermaid
flowchart TB
  subgraph CLI Layer
    CLI[cli/main.py]
    Config[config loader]
  end

  subgraph Core Domain
    Orchestrator[orchestrator.py]
    Matcher[matcher/engine.py]
    Exporter[export/exporter.py]
    Cache[cache/store.py]
    Logging[logging/config.py]
  end

  subgraph Integrations
    JiraClient[clients/jira_client.py]
    BBClient[clients/bitbucket_client.py]
    SecretsClient[clients/secrets_manager_client.py]
  end

  subgraph Agents & Memory
    Agents[agents/ (LangGraph or crewAI)]
    MCP[MCP memory connectors]
    RAG[RAG: FAISS/Vertex AI]
  end

  subgraph Deployment
    Lambda[Lambda handler]
    ECS[ECS task runner]
    S3[(S3)]
    GHActions[GitHub Actions CI]
  end

  CLI --> Orchestrator
  Config --> Orchestrator
  Orchestrator --> JiraClient
  Orchestrator --> BBClient
  Orchestrator --> Matcher
  Matcher --> Exporter
  Orchestrator --> Exporter
  Orchestrator --> Cache
  Logging -. used by .- CLI
  Logging -. used by .- Orchestrator
  SecretsClient --> JiraClient
  SecretsClient --> BBClient

  Orchestrator --> Agents
  Agents --> MCP
  Agents --> RAG

  GHActions --> S3
  Lambda --> Orchestrator
  ECS --> Orchestrator
  Exporter --> S3
```

# Architecture

```mermaid
flowchart LR
    User["User / Recruiter"] --> Web["Next.js demo UI"]
    Web --> Proxy["/api/chat proxy route"]
    Proxy --> API["FastAPI /api/chat/stream"]
    API --> Graph["LangGraph workflow"]
    Graph --> Safety["Prompt injection guard"]
    Graph --> RAG["LlamaIndex + FAISS"]
    Graph --> Tools["Order lookup / Ticket / Discord"]
    Graph --> LLM["OpenAI chat model"]
    API --> DB["SQLite trace logs"]
```

## Data Flow

1. Frontend gửi message qua proxy route để tránh CORS khi deploy.
2. FastAPI chạy LangGraph workflow gồm sanitize, retrieve, tool dispatch, generate.
3. Mọi query/response được log cùng `trace_id` vào SQLite.
4. Kết quả được stream text về frontend, đồng thời gửi metadata tool call qua header.

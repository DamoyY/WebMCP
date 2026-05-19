# web MCP

`web` 是一个 Python 实现的 Streamable HTTP MCP 服务，提供 Exa 搜索、Jina 页面读取，以及页面内正则查找工具。

## 工具

- `search_query`：参数 `requests` 为 `Array<{ q: string, recency?: integer, domains?: string[], category?: string }>`
- `open`：参数 `requests` 为 `Array<{ url: string, chunk?: integer }>`
- `find`：参数 `requests` 为 `Array<{ url: string, pattern: string, snippet_tokens?: integer }>`

调用时通过 HTTP Header 传入 API Key：

- `x-exa-api-key`
- `x-jina-api-key`

## 本地运行

```bash
uv sync
uv run web-mcp
```

默认 MCP endpoint：`http://127.0.0.1:8000/mcp`

生产部署默认 endpoint：`https://the-mars.dog/web-mcp/mcp`

## 检查

```bash
uv run ruff check .
uv run pyright
uv run pytest
```

## 同步到服务器

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sync_to_server.ps1
```

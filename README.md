# web-mcp

web-mcp 是一个基于 Streamable HTTP 传输协议的 MCP 服务。该服务集成了 Exa 网络搜索与 Jina 页面读取功能，允许 LLM 客户端通过标准化工具进行信息检索、网页内容读取及页面内正则表达式匹配。

## 核心功能

*   **网络搜索**：通过 Exa API 执行结构化搜索，支持按域名、时间、分类进行过滤。
*   **网页读取与分块**：将目标网页转换为 Markdown 格式。长文本支持分块（Chunking）按需读取，避免超出 Token 限制。
*   **直接获取机制**：针对特定托管平台（GitHub、HuggingFace、GitLab、Bitbucket、Wikipedia）及纯文本文件，支持绕过渲染直接拉取原始内容。
*   **页面内查找**：支持在指定网页内使用正则表达式搜索内容，并返回包含上下文的文本片段。
*   **容错输入解析**：对客户端提供的非标准或带有别名的输入参数进行自动归一化处理，并通过 `warning` 字段返回修正建议。

## 环境要求

*   Python >= 3.14
*   uv
*   Exa API Key
*   Jina API Key

## 安装与启动

1.  **安装依赖**：
    使用 `uv` 创建虚拟环境、安装项目及开发依赖：
    ```bash
    uv sync
    ```

2.  **配置**：
    系统默认读取当前目录下 `config/default.yaml` 配置文件。可通过环境变量 `WEB_MCP_CONFIG` 指定自定义配置路径：
    ```bash
    export WEB_MCP_CONFIG=/path/to/your/config.yaml
    ```

3.  **启动服务**：
    可直接使用命令启动：
    ```bash
    uv run web-mcp
    ```
    *(注：项目目录下的 `deploy` 文件夹中提供了用于生产环境的 systemd 服务单元和 Nginx 反向代理配置文件。)*

4.  **运行测试**：
    ```bash
    uv run pytest
    ```

## 客户端接入方式

客户端需通过 HTTP(S) 连接服务，并使用 Server-Sent Events (SSE) / Streamable HTTP 建立通信。

请求时**必须**在 HTTP Header 中携带相应的 API 凭据（Header 名称可在配置文件中自定义，以下为默认约定）：

*   `x-exa-api-key`: 用于 `search_query` 工具。
*   `x-jina-api-key`: 用于 `open` 和 `find` 工具（直接拉取机制除外）。

## 可用工具 (Tools)

所有工具的输入参数均需封装在 `requests` 数组中，支持单次调用执行多个同类型请求。

### 1. `search_query`
执行网络搜索，返回包含标题、发布日期、URL 和摘要的搜索结果。

**参数** (`requests` 数组元素):
*   `q` (`string`, 必填): 搜索关键词。
*   `recency` (`int`, 可选): 限定过去多少天内的结果。
*   `domains` (`array[string]`, 可选): 限定搜索的域名范围，例如 `["openai.com"]`。
*   `category` (`string`, 可选): 搜索类别，可选值包括 `company`, `research paper`, `news`, `pdf`, `personal site`, `financial report`, `people`。

### 2. `open`
获取网页的 Markdown 内容。由于页面可能过长，返回内容会根据配置被划分为多个分块（Chunk），客户端需指定读取的分块索引。

**参数** (`requests` 数组元素):
*   `url` (`string`, 必填): 需要读取的绝对 HTTP/HTTPS 网址。
*   `chunk` (`int`, 必填): 读取的分块序号（从 1 开始）。

**返回**:
包含当前分块内容 (`content`)、当前分块序号 (`chunk`) 以及该页面总分块数 (`total_chunks`)。

### 3. `find`
读取网页内容，使用正则表达式搜索匹配项，并返回包含前后上下文的文本片段（Snippet）。

**参数** (`requests` 数组元素):
*   `url` (`string`, 必填): 需要检索的网址。
*   `pattern` (`string`, 必填): 用于匹配的正则表达式。
*   `snippet_tokens` (`int`, 可选): 返回的片段最大 Token 数量。

**返回**:
返回匹配的文本片段列表及它们所在的分块位置。若单页匹配项超过配置上限（默认截断），会停止继续搜索当前页面。

## 输入规范化与警告机制

该服务实现了一层宽松的参数解析器：
*   如果客户端提供了错误的参数名（如 `URL` 代替 `url`，`query` 代替 `q`），或忘记使用 `requests` 数组包裹请求体，服务会尝试自动纠正。
*   发生纠正时，服务响应结果中会包含一个 `warning` 数组，告知客户端正确的参数使用方法，用于辅助 LLM 在后续请求中调整输出结构。

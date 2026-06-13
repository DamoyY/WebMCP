# web-mcp

web-mcp 是一个基于 Streamable HTTP 传输的 MCP（Model Context Protocol）服务。它把网页搜索与网页正文读取封装成可供 MCP 客户端调用的工具，搜索能力由 Exa 提供，网页正文读取能力由 Jina Reader 提供，并对部分站点支持直接抓取原始文本。

## 功能特性

- 提供三个 MCP 工具：`search_query`（搜索）、`open`（读取页面内容）、`find`（在页面中按正则查找片段）。
- 所有工具均支持批量调用，一次请求可携带多个查询或多个链接，服务端并发处理。
- 网页搜索返回标题、发布日期、URL 与内容摘要，可按时间、站点域名、内容类别进行过滤。
- 网页正文读取会将长页面按 token 切分为多个分块，便于按需逐块获取，避免一次返回过多内容。
- 对 GitHub、Hugging Face、Wikimedia、Microsoft Learn 等站点支持直接抓取，无需经过 Jina。
- 对输入参数具有较强的容错能力：可识别常见的字段别名、自动补全缺失的 URL 协议、解析以 JSON 字符串形式传入的参数等，并在响应中以 `warning` 字段提示调整内容。
- 内置健康检查端点，便于部署时做存活探测。

## 环境要求

- Python 3.14 或更高版本。
- 一个 Exa API 密钥（用于搜索）。
- 一个 Jina API 密钥（用于读取非直接抓取站点的网页正文）。

## 安装

在项目根目录执行安装即可，例如：

```bash
pip install .
```

安装后会提供命令行入口 `web-mcp`。

## 配置

服务的运行参数由 YAML 配置文件提供，默认读取当前工作目录下的 `config/default.yaml`。

可通过环境变量 `WEB_MCP_CONFIG` 指定其他配置文件路径：

```bash
export WEB_MCP_CONFIG=/path/to/your/config.yaml
```

配置文件涵盖以下几类内容：

- `server`：服务名称、说明、监听地址与端口、日志级别、Streamable HTTP 路径、健康检查路径等。
- `headers`：用于读取 API 密钥的请求头名称（分别对应 Exa 与 Jina）。
- `search`：搜索返回数量、检索类型、摘要长度等参数。
- `http`：网络请求超时设置。
- `jina`：Jina Reader 的调用参数。
- `chunking`：分块所用的分词器、单块 token 数量与重叠比例。
- `find`：查找片段的默认长度与单页最大匹配数。
- `direct_fetch`：直接抓取的体积上限及各代码托管站点的主机名、可识别的文本扩展名与文件名。

### API 密钥的传递方式

API 密钥不写入配置文件，而是由 MCP 客户端在每次 HTTP 请求中通过请求头携带。请求头的名称在配置文件的 `headers` 部分定义。

- `search_query` 工具要求请求中必须包含 Exa 密钥对应的请求头。
- `open` 与 `find` 工具在访问非直接抓取站点时，要求包含 Jina 密钥对应的请求头；若目标链接属于直接抓取站点，则无需 Jina 密钥。

## 启动服务

使用命令行入口启动：

```bash
web-mcp
```

服务将以 Streamable HTTP 方式对外提供 MCP 接口，监听地址、端口与路径取自配置文件。

服务同时暴露了一个标准的 ASGI 应用对象（`web_mcp.server:app`），也可以使用 ASGI 服务器直接运行，例如：

```bash
uvicorn web_mcp.server:app --host 0.0.0.0 --port 8000
```

### 健康检查

服务在配置指定的健康检查路径上提供一个 GET 端点，返回服务状态与名称，可用于部署环境的存活探测。

## 工具说明

三个工具的入参都是一个名为 `requests` 的数组，数组中的每个元素是一次独立的操作。响应中除业务数据外，可能附带一个 `warning` 字段，用于提示对输入所做的自动修正。

### search_query

执行网页搜索，返回每条结果的标题、日期、URL 与摘要。

每个请求项支持的字段：

- `q`（必填）：查询关键词，不能为空。
- `recency`（可选）：限定只返回最近若干天内发布的结果，取值为正整数（天数）。
- `domains`（可选）：限定搜索的站点域名列表。
- `category`（可选）：限定内容类别，可选值为 `company`、`research paper`、`news`、`pdf`、`personal site`、`financial report`、`people`。

调用示例：

```json
{
  "requests": [
    { "q": "MCP protocol overview" },
    {
      "q": "vector database benchmarks",
      "recency": 30,
      "category": "research paper"
    }
  ]
}
```

### open

读取一个或多个网页的正文内容。长页面会被切分为多个分块，需要通过 `chunk` 指定要获取的分块序号。

每个请求项支持的字段：

- `url`（必填）：要读取的页面地址，需为合法的 HTTP 或 HTTPS 链接。
- `chunk`（必填）：要获取的分块序号，从 1 开始。

返回的每个页面包含当前分块序号、总分块数与该分块的正文内容。若需要读取后续内容，可使用返回的总分块数，递增 `chunk` 再次调用。

调用示例：

```json
{
  "requests": [{ "url": "https://example.com/article", "chunk": 1 }]
}
```

### find

在一个或多个网页中使用正则表达式查找匹配，并返回匹配处附近的文本片段。

每个请求项支持的字段：

- `url`（必填）：要检索的页面地址，需为合法的 HTTP 或 HTTPS 链接。
- `pattern`（必填）：正则表达式，不能为空。
- `snippet_tokens`（可选）：每个匹配片段的长度（以 token 计），为正整数；若超过单块上限，会被自动调整并在 `warning` 中提示。

返回的每个页面包含总分块数与匹配列表，每条匹配包含其所在分块序号与片段文本。单页返回的匹配数量受配置上限约束。

调用示例：

```json
{
  "requests": [
    {
      "url": "https://example.com/docs",
      "pattern": "install(ation)?",
      "snippet_tokens": 80
    }
  ]
}
```

## 直接抓取支持的站点

对于以下类型的链接，`open` 与 `find` 会直接抓取原始文本，无需 Jina 密钥：

- GitHub 及其原始内容域名上的文本文件（如仓库 blob 链接、raw 链接、Gist）。
- Hugging Face 上仓库、数据集、Space 中的文本文件。
- GitLab 与 Bitbucket 仓库中的文本文件。
- Wikimedia 各项目（包括 Wikipedia、Wiktionary、Wikimedia Commons、Wikidata 等）的页面，以及 Fandom 页面。
- Microsoft Learn 文档页面（取其 Markdown 版本）。
- PyPI、npm 与 crates.io 的包页面。

托管站点中的文件是否被识别为文本文件，取决于配置中列出的扩展名与文件名。其余站点的链接则通过 Jina Reader 读取，此时需要提供 Jina 密钥。

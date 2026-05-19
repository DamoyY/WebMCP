from __future__ import annotations
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from web_mcp.config import AppConfig, load_config
from web_mcp.tools import register_tools


def create_mcp(config: AppConfig | None = None) -> FastMCP:
    app_config = config or load_config()
    server_config = app_config.server
    mcp = FastMCP(
        name=server_config.name,
        instructions=server_config.instructions,
        host=server_config.host,
        port=server_config.port,
        log_level=server_config.log_level,
        streamable_http_path=server_config.streamable_http_path,
        stateless_http=server_config.stateless_http,
        json_response=server_config.json_response,
    )
    register_tools(mcp, app_config)

    @mcp.custom_route(server_config.health_path, methods=["GET"])
    async def health_check(_request: Request) -> Response:
        return JSONResponse({"status": "ok", "name": server_config.name})

    return mcp


mcp = create_mcp()
app = mcp.streamable_http_app()


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()

def main() -> None:
    import uvicorn

    from cora.config import get_settings

    settings = get_settings()
    uvicorn.run("cora.api.main:app", host=settings.api_host, port=settings.api_port)

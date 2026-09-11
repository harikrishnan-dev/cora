def main() -> None:
    import uvicorn

    from it_man.config import get_settings

    settings = get_settings()
    uvicorn.run("it_man.api.main:app", host=settings.api_host, port=settings.api_port)

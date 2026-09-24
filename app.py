"""QAROZ executable entry point."""

from qa_manager.main import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn

    from qa_manager.core.config import get_settings

    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)

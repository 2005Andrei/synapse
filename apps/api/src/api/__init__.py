def main() -> None:
    """`uv run api`: start the HTTP API with auto-reload."""
    import uvicorn

    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=True)

from fastapi import FastAPI

app = FastAPI(title="Hopitalia Budget")


@app.get("/health")
def health() -> dict[str, str]:
    return {"statut": "ok"}

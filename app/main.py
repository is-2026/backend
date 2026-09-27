from fastapi import FastAPI

app = FastAPI(
    title="Backend API",
    version="0.1.0",
)


@app.get("/")
def root():
    return {"message": "Backend funcionando"}

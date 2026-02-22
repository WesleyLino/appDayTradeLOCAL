from fastapi import FastAPI
import uvicorn
import sys

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.on_event("startup")
def startup_event():
    print("TEST SERVER STARTED", file=sys.stderr)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)

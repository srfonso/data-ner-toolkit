import uvicorn
from settings import MAX_WORKERS

# ======================================================
# =====         RUN REST API WITH UVICORN          =====
# ======================================================
if __name__ == "__main__":
    uvicorn.run("src.api:app", workers=MAX_WORKERS)

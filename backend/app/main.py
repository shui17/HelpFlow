from fastapi import FastAPI

app = FastAPI(title="HelpFlow")


@app.get("/")
async def root():
    return {
        "message": "欢迎使用 HelpFlow 客服工单系统"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "ok"
    }
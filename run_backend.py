"""
MiniFin 后端启动脚本 — 双击运行即可启动服务。
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8765, reload=True)

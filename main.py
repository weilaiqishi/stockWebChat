# -*- coding: utf-8 -*-
"""Stock Web Chat — AI Agent 策略问股 启动入口."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )

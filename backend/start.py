"""Production entry point for Render and containers. Run migrations separately."""
import os

import uvicorn


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")),
                proxy_headers=True)

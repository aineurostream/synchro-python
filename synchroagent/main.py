import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from synchroagent.api import clients, configs, events
from synchroagent.config import default_config

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("synchroagent")


app = FastAPI(
    title="SynchroAgent API",
    description="API for managing Synchro clients and configurations",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clients.router, prefix="/api/clients", tags=["clients"])
app.include_router(configs.router, prefix="/api/configs", tags=["configs"])
app.include_router(events.router, prefix="/api/events", tags=["events"])


if __name__ == "__main__":
    uvicorn.run(
        "synchroagent.main:app",
        host=default_config.api_host,
        port=default_config.api_port,
        reload=True,
    )

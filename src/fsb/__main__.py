import logging

import uvicorn
from fusion_core.proc import set_process_title

from .config import fsb_config

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    host = fsb_config.SERVER_HOST
    port = fsb_config.SERVER_PORT
    set_process_title(f"fusion-smallbusiness serve :{port}")
    logger.info("fsb server starting on %s:%s", host, port)
    uvicorn.run(
        "fsb.app:app",
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()

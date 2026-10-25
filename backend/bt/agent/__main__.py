"""Entry point: `python -m bt.agent` — single-process worker with clean SIGTERM/SIGINT shutdown."""
import logging
import os
import signal

from ..db import init_db
from .loop import Worker


def main() -> None:
    logging.basicConfig(level=os.environ.get("BT_LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    init_db()
    worker = Worker()

    def _stop(signum, _frame):
        logging.getLogger("bt.agent").info("signal %s — shutting down", signum)
        worker.rt.stop_requested = True
        # Interrupt any blocking call (LLM/yt-dlp/sleep) right away; Worker.run's finally sets state offline.
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    worker.run()


if __name__ == "__main__":
    main()

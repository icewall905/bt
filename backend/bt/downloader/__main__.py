"""Entry point: `python -m bt.downloader` — one download at a time, clean SIGTERM/SIGINT shutdown."""
import logging
import os
import signal

from ..db import init_db
from .service import Downloader


def main() -> None:
    logging.basicConfig(level=os.environ.get("BT_LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    init_db()
    dl = Downloader()

    def _stop(signum, _frame):
        logging.getLogger("bt.downloader").info("signal %s — shutting down", signum)
        dl.stop.set()
        # Interrupts a running yt-dlp download right away; Downloader.run's finally re-queues it (resumable .part).
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    dl.run()


if __name__ == "__main__":
    main()

import logging
import sys
import ctx

class CtxFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = ctx.correlation_id.get("-")
        record.query_id = ctx.query_id.get("-")
        return True

def setup_logging(level: str = "INFO") -> None:
    try:
        from pythonjsonlogger.json import JsonFormatter
        fmt = JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(correlation_id)s %(query_id)s"
        )
    except ImportError:
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(fmt)
    h.addFilter(CtxFilter())

    logging.root.setLevel(getattr(logging, level.upper(), logging.INFO))
    logging.root.handlers.clear()
    logging.root.addHandler(h)

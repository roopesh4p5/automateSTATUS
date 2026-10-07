"""Office network health check modules."""

from .dns import check_dns
from .gateway import check_gateway
from .internet import check_internet
from .latency import check_latency_and_loss
from .speed import check_speed

__all__ = [
    "check_gateway",
    "check_dns",
    "check_latency_and_loss",
    "check_internet",
    "check_speed",
]

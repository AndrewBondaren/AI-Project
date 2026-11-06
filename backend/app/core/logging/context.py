"""Request correlation shared by all logging consumers."""
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

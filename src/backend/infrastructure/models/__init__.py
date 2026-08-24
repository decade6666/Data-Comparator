from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from .comparison_run import ComparisonRun  # noqa: E402,F401
from .recycled_config import RecycledConfig  # noqa: E402,F401
from .user import User  # noqa: E402,F401

"""Runs only INSIDE a one-shot, networkless, non-root sandbox container."""

import datetime
import json
import math
import re
import sys
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if not TYPE_CHECKING:
    import numpy as np
    import pandas as pd

    pd.set_option("display.max_columns", 20)
    pd.set_option("display.width", 1000)
else:
    np: Any = None
    pd: Any = None
# The container is the security boundary; Python builtin restrictions are not a sandbox.
namespace = {
    "__name__": "__main__",
    "math": math,
    "datetime": datetime,
    "json": json,
    "re": re,
    "Decimal": Decimal,
    "np": np,
    "pd": pd,
}
exec(compile(sys.argv[1], "<sandbox>", "exec"), namespace)

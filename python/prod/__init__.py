from defipy.erc import *
from defipy.math.basic import *
from defipy.math.interest import *
from defipy.math.interest.ips import *
from defipy.math.interest.ips.aggregate import *
from defipy.math.model import *
from defipy.math.risk import *
from defipy.process import *
from defipy.process.burn import *
from defipy.process.deposit import *
from defipy.process.liquidity import *
from defipy.process.mint import *
from defipy.process.swap import *
from defipy.process.join import *
from defipy.analytics.simulate import *
from defipy.analytics.risk import *
from defipy.utils.interfaces import *
from defipy.utils.data import *
from defipy.utils.client import *
from defipy.utils.client.contract import *
from defipy.utils.tools import *

# Agent modules require web3scout, available via the [book] extra.
# If web3scout (or any of its transitive deps like a specific web3.py
# surface) isn't satisfied, skip agent imports so core defipy
# (primitives, math, analytics) remains usable.
try:
    from defipy.agents.config import *
    from defipy.agents.data import *
    from defipy.agents import *
except ImportError as _agent_import_err:
    import warnings as _warnings
    _warnings.warn(
        "defipy.agents could not be imported ({}). Agents require "
        "web3scout + a compatible web3.py; install with: "
        "pip install defipy[book]".format(_agent_import_err),
        ImportWarning,
        stacklevel=2,
    )
    del _warnings
    del _agent_import_err

from defipy.primitives import *
from defipy.primitives.position import *

from uniswappy.cpt.exchg import *
from uniswappy.cpt.factory import *
from uniswappy.cpt.index import *
from uniswappy.cpt.quote import *
from uniswappy.cpt.vault import *
from uniswappy.cpt.wallet import *
from uniswappy.utils.tools.v3 import *

from stableswappy.quote import *
from stableswappy.vault import *
from stableswappy.cst.factory import *
from stableswappy.cst.exchg import *
from stableswappy.utils.data import StableswapExchangeData

from balancerpy.quote import *
from balancerpy.vault import *
from balancerpy.cwpt.factory import *
from balancerpy.cwpt.exchg import *
from balancerpy.enums import *
from balancerpy.utils.data import BalancerExchangeData



  
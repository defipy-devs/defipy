# ─────────────────────────────────────────────────────────────────────────────
# Apache 2.0 License (DeFiPy)
# ─────────────────────────────────────────────────────────────────────────────
# Copyright 2023–2025 Ian Moore
# Email: defipy.devs@gmail.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from uniswappy.process.join import Join as UniswapJoin
from balancerpy.process.join import Join as BalancerJoin
from stableswappy.process.join import Join as StableswapJoin

class Join():
    
    """ Process to join x and y amounts to pool              
    """       

    def __init__(self):
        pass

    def apply(self, lp, v1 = None, v2 = None, v3 = None, v4 = None, v5 = None):
        """ apply

            Join x and y amounts to pool

            UniswapJoin().apply(lp, user_nm, amount0, amount1, lwr_tick = None, upr_tick = None):
            
            BalancerJoin().apply(lp, user_nm, shares)
            
            StableswapJoin().apply(lp, user_nm, shares)
                     
            Returns
            -------
            out : dictionary
                join output               
        """ 

        if type(lp).__name__ == 'UniswapExchange' or type(lp).__name__ == 'UniswapV3Exchange':
            out = UniswapJoin().apply(lp, v1, v2, v3, v4, v5)
        elif type(lp).__name__ == 'BalancerExchange':
            out = BalancerJoin().apply(lp, v1, v2)     
        elif type(lp).__name__ == 'StableswapExchange':
            out = StableswapJoin().apply(lp, v1, v2)     
        else:
            print('DeFiPy: WRONG EXCHANGE TYPE OR VARIABLES')
             
        return out 

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

from uniswappy.process.swap import Swap as UniswapSwap
from balancerpy.process.swap import Swap as BalancerSwap
from stableswappy.process.swap import Swap as StableswapSwap

class Swap():
    
    """ Process to swap token X for token Y (and vice verse)            
    """       

    def __init__(self, global_var1 = None):
        self.gvar = global_var1

    def apply(self, lp, v1 = None, v2 = None, v3 = None, v4 = None):
        """ apply

            Swap token X for token Y (and vice verse)  

            UniswapSwap().apply(lp, token_in, user_nm, amount)
            
            BalancerSwap().apply(lp, token_in, token_out, user_nm, amount)
            
            StableswapSwap().apply(lp, token_in, token_out, user_nm, amount)
                     
            Returns
            -------
            out : dictionary
                join output               
        """ 

        if type(lp).__name__ == 'UniswapExchange' or type(lp).__name__ == 'UniswapV3Exchange':
            out = UniswapSwap().apply(lp, v1, v2, v3)
        elif type(lp).__name__ == 'BalancerExchange':
            out = BalancerSwap(self.gvar).apply(lp, v1, v2, v3, v4)     
        elif type(lp).__name__ == 'StableswapExchange':
            out = StableswapSwap().apply(lp, v1, v2, v3, v4)     
        else:
            print('DeFiPy: WRONG EXCHANGE TYPE OR VARIABLES')
             
        return out 

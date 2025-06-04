# Copyright [2025] [Ian Moore]
# Distributed under the MIT License (license terms are at http://opensource.org/licenses/MIT).
# Email: defipy.devs@gmail.com

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

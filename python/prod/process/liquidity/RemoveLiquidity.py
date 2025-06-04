# Copyright [2025] [Ian Moore]
# Distributed under the MIT License (license terms are at http://opensource.org/licenses/MIT).
# Email: defipy.devs@gmail.com

from uniswappy.process.liquidity import RemoveLiquidity as UniswapRemoveLiquidity
from balancerpy.process.liquidity import RemoveLiquidity as BalancerRemoveLiquidity
from stableswappy.process.liquidity import RemoveLiquidity as StableswapRemoveLiquidity

class RemoveLiquidity():
    
    """ Process to join x and y amounts to pool              
    """       

    def __init__(self, global_var1 = None):
        self.gvar = global_var1

    def apply(self, lp, v1 = None, v2 = None, v3 = None, v4 = None, v5 = None):
        """ apply

            Join x and y amounts to pool

            UniswapRemoveLiquidity().apply(lp, user_nm, amount0, amount1, lwr_tick = None, upr_tick = None):
            
            BalancerRemoveLiquidity(Proc.ADDTKN).apply(lp, tkn_in, user_nm, amt_tkn_in)
            
            StableswapRemoveLiquidity().apply(lp, tkn_in, user_nm, amt_tkn_in)
                     
            Returns
            -------
            out : dictionary
                join output               
        """ 

        if type(lp).__name__ == 'UniswapExchange' or type(lp).__name__ == 'UniswapV3Exchange':
            out = UniswapRemoveLiquidity().apply(lp, v1, v2, v3, v4, v5)
        elif type(lp).__name__ == 'BalancerExchange':
            out = BalancerRemoveLiquidity(self.gvar).apply(lp, v1, v2, v3)     
        elif type(lp).__name__ == 'StableswapExchange':
            out = StableswapRemoveLiquidity().apply(lp, v1, v2, v3)     
        else:
            print('DeFiPy: WRONG EXCHANGE TYPE OR VARIABLES')
             
        return out 

# Copyright [2025] [Ian Moore]
# Distributed under the MIT License (license terms are at http://opensource.org/licenses/MIT).
# Email: defipy.devs@gmail.com

from uniswappy.process.liquidity import AddLiquidity as UniswapAddLiquidity
from balancerpy.process.liquidity import AddLiquidity as BalancerAddLiquidity
from stableswappy.process.liquidity import AddLiquidity as StableswapAddLiquidity

class AddLiquidity():
    
    """ Add liquidity process             
    """       

    def __init__(self, global_var1 = None):
        self.gvar = global_var1

    def apply(self, lp, v1 = None, v2 = None, v3 = None, v4 = None, v5 = None):
        """ apply

            Add liquidity process

            UniswapAddLiquidity().apply(lp, user_nm, amount0, amount1, lwr_tick = None, upr_tick = None):
            
            BalancerAddLiquidity(Proc.ADDTKN).apply(lp, tkn_in, user_nm, amt_tkn_in)
            
            StableswapAddLiquidity().apply(lp, tkn_in, user_nm, amt_tkn_in)
                     
            Returns
            -------
            out : dictionary
                join output               
        """ 

        if type(lp).__name__ == 'UniswapExchange' or type(lp).__name__ == 'UniswapV3Exchange':
            out = UniswapAddLiquidity().apply(lp, v1, v2, v3, v4, v5)
        elif type(lp).__name__ == 'BalancerExchange':
            out = BalancerAddLiquidity(self.gvar).apply(lp, v1, v2, v3)     
        elif type(lp).__name__ == 'StableswapExchange':
            out = StableswapAddLiquidity().apply(lp, v1, v2, v3)     
        else:
            print('DeFiPy: WRONG EXCHANGE TYPE OR VARIABLES')
             
        return out 

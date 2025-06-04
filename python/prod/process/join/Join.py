# Copyright [2024] [Ian Moore]
# Distributed under the MIT License (license terms are at http://opensource.org/licenses/MIT).
# Email: defipy.devs@gmail.com

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

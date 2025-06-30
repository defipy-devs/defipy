# Copyright [2025] [Ian Moore]
# Distributed under the MIT License (license terms are at http://opensource.org/licenses/MIT).
# Email: defipy.devs@gmail.com

from uniswappy.utils.tools.v3 import UniV3Helper
from uniswappy.process.swap import WithdrawSwap
from uniswappy.process.deposit import SwapDeposit

class UniswapScriptHelper():

    
    """ Uniswap script helper functions             
    """       

    def __init__(self):
        pass

    def calc_arb(self, lp, sDel, tkn_x, tkn_y, user_nm, p):  
        swap_dx, swap_dy = sDel.calc(p, 1, 1)
        direction = 0;
    
        if(swap_dx >= 0):
            expected_amount_dep = SwapDeposit().apply(lp, tkn_x, user_nm, abs(swap_dx))
            expected_amount_out = WithdrawSwap().apply(lp, tkn_y, user_nm, abs(swap_dy))
            dep_tkn_x = abs(swap_dx); wd_tkn_x = 0
            wd_tkn_y = abs(swap_dy); dep_tkn_y = 0
            direction = 0
        elif(swap_dy >= 0):
            expected_amount_dep = SwapDeposit().apply(lp, tkn_y, user_nm, abs(swap_dy))
            expected_amount_out = WithdrawSwap().apply(lp, tkn_x, user_nm, abs(swap_dx)) 
            dep_tkn_y = abs(swap_dy); wd_tkn_y = 0
            wd_tkn_x = abs(swap_dx); dep_tkn_x = 0
            direction = 1
        
        dep_tkn_x = UniV3Helper().dec2gwei(dep_tkn_x)
        dep_tkn_y = UniV3Helper().dec2gwei(dep_tkn_y)
        wd_tkn_x = UniV3Helper().dec2gwei(wd_tkn_x)
        wd_tkn_y = UniV3Helper().dec2gwei(wd_tkn_y)
    
        return (dep_tkn_x, dep_tkn_y, wd_tkn_x, wd_tkn_y, direction)
    
    def calc_arb_contract(self, lp, sDel, tkn_x, tkn_y, user_nm, p):  
        swap_dx, swap_dy = sDel.calc(p, 1, 1)
        direction = 0;
    
        if(swap_dx >= 0):
            dep_tkn_x = abs(swap_dx); wd_tkn_x = 0
            wd_tkn_y = abs(swap_dy); dep_tkn_y = 0
            direction = 0
        elif(swap_dy >= 0):
            dep_tkn_y = abs(swap_dy); wd_tkn_y = 0
            wd_tkn_x = abs(swap_dx); dep_tkn_x = 0
            direction = 1
        
        dep_tkn_x = UniV3Helper().dec2gwei(dep_tkn_x)
        dep_tkn_y = UniV3Helper().dec2gwei(dep_tkn_y)
        wd_tkn_x = UniV3Helper().dec2gwei(wd_tkn_x)
        wd_tkn_y = UniV3Helper().dec2gwei(wd_tkn_y)
    
        return (dep_tkn_x, dep_tkn_y, wd_tkn_x, wd_tkn_y, direction)

    def pool_state(self, pool_contract, verbose=False):
        reserves = pool_contract.functions.getReserves().call() 
        lp_amt = pool_contract.functions.totalSupply().call() 
        if(verbose): 
            print(f'TKN0 {UniV3Helper().gwei2dec(reserves[0]):.2f} / TKN1 {UniV3Helper().gwei2dec(reserves[1]):.2f} / Liquidity {UniV3Helper().gwei2dec(lp_amt):.2f}') 
        return (reserves[0], reserves[1], lp_amt)
# StableswapExchange.py
# Author: Ian Moore ( imoore@syscoin.org )
# Date: Oct 2023

from decimal import Decimal
from python.prod.group import StableswapERC20Group
from python.prod.cst.factory import StableswapFactory
from python.prod.cst.exchg.StableswapPoolMath import StableswapPoolMath 

import math

GWEI_PRECISION = 18
GWEI_SWAP_FEE = 1000000
MINIMUM_LIQUIDITY = 1e-15
EXIT_FEE = 0

class StableswapExchange():
    
    def __init__(self, creator: StableswapFactory, tkn_group : StableswapERC20Group, symbol: str, addr : str) -> None:     
        self.factory = creator
        self.tkn_group = tkn_group
        self.name = tkn_group.get_name()
        self.symbol = symbol 
        self.addr = addr   
        self.tkn_reserves = {}
        self.tkn_decimals = {}
        self.tkn_fees = {}
        self.collected_fees = {}
        self.liquidity_providers = {}  
        self.total_supply = 0
        self.last_liquidity_deposit = 0
        self.math_pool = None
        self.joined = False 
        
    def info(self):
        if(self.total_supply == 0):
            print(f"Stableswap Exchange: {self.name} ({self.symbol})")
            print(f"Coins: {self.tkn_group.get_coins_str()}")
            print(f"Liquidity: {self.total_supply} \n")             
        else:
            reserve_str = " | ".join([f'{tkn_nm} = {self.tkn_reserves[tkn_nm]:.2f}' for tkn_nm in self.tkn_reserves]) 
            print(f"Stableswap Exchange: {self.name} ({self.symbol})")
            print(f"Coins: {self.tkn_group.get_coins_str()}")
            print(f"Reserves: {reserve_str}")
            print(f"Liquidity: {self.total_supply} \n") 
            
    def join_pool(self, tkn_group : StableswapERC20Group, ampl_coeff : float, to: str):
        
        """ join_pool

            Initialize a Stableswap pool, and add liquidity for all asset deposit
                
            Parameters
            -------
            tkn_group : StableswapERC20Group
                Group of ERC20 objects     
            amt_shares_in : float
                Amount of pool shares in      
            to : str
                User name/address                 
        """          
        
        if(not self.joined):
            self.tkn_group = tkn_group
            self.tkn_reserves = tkn_group.get_balances().copy()
            self.tkn_decimals = tkn_group.get_decimals().copy()

            decimal_amts = list(self.tkn_group.get_decimal_amts().values())
            rates = list(self.tkn_group.get_rates().values())

            self.math_pool = StableswapPoolMath(A = ampl_coeff, D = decimal_amts, n = len(rates), 
                                                rates = rates, fee = GWEI_SWAP_FEE)     
            amt_liquidity_in = self._dec2amt(self.math_pool.tokens, GWEI_PRECISION) 
            
            if self.total_supply == 0:
                self._mint('init_account', MINIMUM_LIQUIDITY) 
                amt_liquidity_in = amt_liquidity_in - MINIMUM_LIQUIDITY
                           
            self._mint(to, amt_liquidity_in)
            self.joined = True
        else:
            assert not self.joined, 'Stableswap V1: POOL ALREADY JOINED'   
            
    def swap(self, amt_tkn_in, tkn_in, tkn_out, to):
        
        """ swap

            Swap output token given input token 
                
            Parameters
            -------
            amt_tkn_in : float
                Amount of input token requested for swaping   
            tkn_in : ERC20
                Input token           
            tkn_out : ERC20
                Output token                    
            to : str
                User name/address                 
        """          
        
        assert self.tkn_group.get_token(tkn_in.token_name) and self.tkn_group.get_token(tkn_out.token_name), "Stableswap: TOKEN NOT PART OF GROUP"
        amount_out = self.get_amount_out(amt_tkn_in, tkn_in, tkn_out)
        assert amount_out['tkn_out_amt'] <= tkn_out.token_total, 'Stableswap V1: INSUFFICIENT_OUTPUT_AMOUNT'   
    
        self._swap_math_pool(amt_tkn_in, tkn_in, tkn_out)    
        self.tkn_group.get_token(tkn_in.token_name).deposit(to, amt_tkn_in)
        self._swap(amount_out['tkn_out_amt'], amount_out['tkn_in_fee'], tkn_out, tkn_in, to)
        self._tally_fees(tkn_in, amount_out['tkn_in_fee'])
        
        return amount_out
    
    def add_liquidity(self, tkn_amt_in, tkn_in, to):
        
        """ add_liquidity

            Add token amounts for LP token
                
            Parameters
            -------
            Parameters
            -------
            amt_shares_in : float
                Amount of pool shares coming in     
            tkn_in : ERC20
                Input token     
            to : str
                User name/address                  
        """    
        
        assert self.tkn_group.get_token(tkn_in.token_name), 'Stableswap V1: TOKEN NOT PART OF GROUP'
        
        tkn_amts_in = [len(self.tkn_reserves)]*5
    
        tkn_in_index = self._get_tkn_index(tkn_in.token_name)
        dec_tkn_in = self.tkn_decimals[tkn_in.token_name]
        tkn_in_dec = self._amt2dec(tkn_amt_in, dec_tkn_in)
        
        tkn_amts_in[tkn_in_index] = tkn_in_dec
        out = self.math_pool.add_liquidity(tkn_amts_in)
        liquidity_amt_in = self._dec2amt(out, GWEI_PRECISION)
        
        self.tkn_group.get_token(tkn_in.token_name).deposit(to, tkn_amt_in)        
        self.mint(liquidity_amt_in, tkn_amt_in, tkn_in, to)
        self._tally_fees(tkn_in, 0)
        
        return {'liquidity_amt_in': liquidity_amt_in, 'tkn_in_nm': tkn_in.token_name}
        
    def remove_liquidity(self, liquidity_amt_out, tkn_out, to):
        
        """ remove_liquidity

            Remove liquidity from specified token in the pool based on lp amount
                
            Parameters
            -------
            to : str
                receiving user address  
            liquidity_amt_out : float
                lp amount to removed                 
            tkn_out : ERC20
                Output token                
        """  
        
        assert self.tkn_group.get_token(tkn_out.token_name), 'Stableswap V1: TOKEN NOT PART OF GROUP'
        
        total_liquidity = self.liquidity_providers[to]
        if liquidity_amt_out >= total_liquidity:
            liquidity_amt_out = total_liquidity          
        
        tkn_out_index = self._get_tkn_index(tkn_out.token_name)
        dec_tkn_out = self.tkn_decimals[tkn_out.token_name]
        liquidity_out_dec = self._amt2dec(liquidity_amt_out, GWEI_PRECISION)  
        
        dout, fee = self.math_pool.calc_withdraw_one_coin(liquidity_out_dec, tkn_out_index, True)
        tkn_amt_out_min = self._dec2amt(dout, dec_tkn_out)

        assert tkn_amt_out_min <= self.tkn_reserves[tkn_out.token_name], 'Stableswap V1: INSUFFICIENT TKN AMOUNT'
        
        tkn_out_dec, tkn_out_fee_dec = self.math_pool.remove_liquidity_one_coin(liquidity_out_dec, tkn_out_index, True)
        tkn_out_amt = self._dec2amt(tkn_out_dec, dec_tkn_out)
        tkn_out_fee = self._dec2amt(tkn_out_fee_dec, dec_tkn_out)

        self.burn(liquidity_amt_out, tkn_out_amt, tkn_out, to)
        self._tally_fees(tkn_out, tkn_out_fee)
        
        return {'tkn_out_amt': tkn_out_amt, 'tkn_out_nm': tkn_out.token_name, 'tkn_out_fee':tkn_out_fee} 
        
        
    def burn(self, liquidity_out, tkn_out_amt, tkn_out, _from):
        
        """ burn

            Burn liquidity from token based on amount of liquidity and amount of token
                
            Parameters
            -------
            liquidity_out : float
                Amount of liquidity requested for burn              
            amt_tkn_out : float
                Amount of token requested for burn    
            tkn_out : ERC20
                Output token     
            _from : str
                User name/address                 
        """          
        
        assert self.tkn_group.get_token(tkn_out.token_name), 'Stableswap V1: TOKEN NOT PART OF GROUP'
        
        self._burn(_from, liquidity_out)
        self.tkn_group.get_token(tkn_out.token_name).transfer(_from, tkn_out_amt)
        new_balance = self.tkn_group.get_token(tkn_out.token_name).token_total
        self._update(new_balance, tkn_out.token_name) 
        
    def _burn(self, _from, liquidity_out):
        
        """ burn

            Burn liquidity from token based on amount of liquidity
                
            Parameters
            -------
            liquidity_out : float
                Amount of liquidity requested for burn        
            _from : str
                User name/address                 
        """         
        
        exit_fee = liquidity_out * EXIT_FEE
        available_liquidity = self.liquidity_providers.get(_from)
        self.liquidity_providers[_from] = available_liquidity - liquidity_out - exit_fee
        self.total_supply -= liquidity_out - exit_fee            
    
    def _swap(self, amt_swap, amt_fee, tkn_out, tkn_in, to): 
        
        """ _swap

            Swap output token given input token 
                
            Parameters
            -------
            amt_out : float
                Amount of input token requested for swaping   
            tkn_in : ERC20
                Input token           
            tkn_out : ERC20
                Output token                    
            to : str
                User name/address                 
        """         
        
        self.tkn_group.get_token(tkn_out.token_name).transfer(to, amt_swap)
        new_tkn_balances = self.tkn_group.get_balances()
        
        res_balance_in = self.tkn_reserves[tkn_in.token_name]
        res_balance_out = self.tkn_reserves[tkn_out.token_name]
        
        new_balance_in = new_tkn_balances[tkn_in.token_name]
        new_balance_out = new_tkn_balances[tkn_out.token_name]
        
        if new_balance_in > res_balance_in - amt_swap:
            amount_in = new_balance_in - res_balance_in
        else:
            amount_in = 0
            
        assert amount_in > 0, 'Stableswap V1: INSUFFICIENT_INPUT_AMOUNT'        
        
        res_balance_in_adjusted = res_balance_in + amount_in 
        res_balance_out_adjusted = res_balance_out - amt_swap
              
        lside = round(math.ceil(res_balance_in_adjusted * res_balance_out_adjusted), 8)
        rside = round(math.ceil(new_balance_in * new_balance_out), 8)     
        
        assert lside  ==  rside , 'Stableswap V1: LP BALANCES NOT ALIGNED TO TKN BALANCES'
        
        self._update(new_balance_in, tkn_in.token_name)
        self._update(new_balance_out, tkn_out.token_name)
        self._tally_fees(tkn_in, amt_fee)    
        
        
    def _swap_math_pool(self, amt_tkn_in, tkn_in, tkn_out): 
        
        """ swap_math_pool

            Given some amount of an asset, quotes an equivalent amount of the other asset
                
            Parameters
            -------
            amt_tkn_in : float
                Amount of token requested for quote            
            tkn_in : ERC20
                Input token                    
            tkn_out : ERC20
                Output token                    
        """          
        
        assert self.tkn_group.get_token(tkn_in.token_name), 'Stableswap V1: TOKEN NOT PART OF GROUP'
        
        ind_tkn_in = self._get_tkn_index(tkn_in.token_name)
        ind_tkn_out = self._get_tkn_index(tkn_out.token_name)
        
        dec_tkn_in = self.tkn_decimals[tkn_in.token_name]
        dec_tkn_out = self.tkn_decimals[tkn_out.token_name]
        
        dx_tkn_in_dec = self._amt2dec(amt_tkn_in, dec_tkn_in)
        out = self.math_pool.exchange(ind_tkn_in, ind_tkn_out, dx_tkn_in_dec)
        
        tkn_out_amt = self._dec2amt(out[0], dec_tkn_out)
        tkn_in_fee = self._dec2amt(out[1], dec_tkn_out) 
        
        return {'tkn_out_amt': tkn_out_amt, 'tkn_in_nm': tkn_in.token_name, 'tkn_in_fee': tkn_in_fee}        
    
    def get_amount_out(self, amt_tkn_in, tkn_in, tkn_out):  
        
        """ get_amount_out

            Given some amount of an asset, quotes an equivalent amount of the other asset
                
            Parameters
            -------
            amt_tkn_in : float
                Amount of token requested for quote            
            tkn_in : ERC20
                Input token                    
            tkn_out : ERC20
                Output token                    
        """          
        
        assert self.tkn_group.get_token(tkn_in.token_name), 'Stableswap V1: TOKEN NOT PART OF GROUP'
        
        ind_tkn_in = self._get_tkn_index(tkn_in.token_name)
        ind_tkn_out = self._get_tkn_index(tkn_out.token_name)
        
        dec_tkn_in = self.tkn_decimals[tkn_in.token_name]
        dec_tkn_out = self.tkn_decimals[tkn_out.token_name]
        
        dx_tkn_in_dec = self._amt2dec(amt_tkn_in, dec_tkn_in)
        out = self.math_pool.get_amount_out(ind_tkn_in, ind_tkn_out, dx_tkn_in_dec)
        
        tkn_out_amt = self._dec2amt(out[0], dec_tkn_out)
        tkn_in_fee = self._dec2amt(out[1], dec_tkn_out) 
        
        return {'tkn_out_amt': tkn_out_amt, 'tkn_in_nm': tkn_in.token_name, 'tkn_in_fee': tkn_in_fee}
        
    
    def mint(self, new_liquidity, amt_tkn_in, tkn_in, to): 
        
        """ mint

            Update reserve amount for specific token in the pool
                
            Parameters
            -------
            new_shares : float
                Amount of new pool shares requested for minting   
            amt_tkn_in : float
                Input token           
            tkn_in : ERC20
                Output token                    
            to : str
                User name/address                 
        """          
        
        tkn_balance = self.tkn_group.get_token(tkn_in.token_name).token_total
        _amt_tkn_in = tkn_balance - self.tkn_reserves[tkn_in.token_name]
        
        assert round(_amt_tkn_in,5) == round(amt_tkn_in,5), 'Stableswap V1: MINT ERROR'
        
        new_balance = tkn_in.token_total
        self._update(new_balance, tkn_in.token_name)
        self._mint(to, new_liquidity)    
    
    def _tally_fees(self, tkn, fee):
        
        
        """ _tally_fees

            Tally fee from swap and record last collected fee
                
            Parameters
            -------   
            tkn : ERC20
                Token where fees are being collected for     
            fee : float
                Fee being collected                
        """         
        
        if tkn.token_name not in self.tkn_fees:
            self.tkn_fees[tkn.token_name] = 0
         
        self.tkn_fees[tkn.token_name] += fee      
   
    def _mint(self, to, value):
        
        """ _mint

            Update reserve amount for specific token in the pool
                
            Parameters
            -------
            value : float
                Amount of new pool shares requested for minting                     
            to : str
                User name/address                 
        """      
                        
        if self.liquidity_providers.get(to):
            self.liquidity_providers[to] += value
        else:
            self.liquidity_providers[to] = value

        self.last_liquidity_deposit = value     
        self.total_supply += value  
        
    def _update(self, new_balance, tkn_nm):
        
        """ _update

            Update reserve amounts specified token
                
            Parameters
            -------   
            new_balance : float
                New reserve amount of token      
            tkn_nm : ERC20
                Name of token being updated                  
        """          
        
        self.tkn_reserves[tkn_nm] = new_balance             
        
    def _get_tkn_index(self, tkn_nm):
        return list(self.tkn_reserves.keys()).index(tkn_nm)
        
    def _amt2dec(self, tkn_amt, decimal):
        return int(Decimal(str(tkn_amt))*Decimal(str(10**decimal)))
    
    def _dec2amt(self, dec_amt, decimal):        
        return float(Decimal(str(dec_amt))/Decimal(str(10**decimal)))    
            
    def get_math_pool(self):
        return self.math_pool
    
    def get_reserve_decimal_amts(self):
        decimal_amts = {}
        token_decimals = self.tkn_group.get_decimals()
        for tkn_nm in token_decimals:
            tkn_amt = self.tkn_reserves[tkn_nm]
            decimal_amts[tkn.token_name] = self._amt2dec(tkn_amt, tkn.token_decimal) 
        return decimal_amts  
 

    def get_price(self, base_tkn, opp_tkn, fee = False):
        
        """ get_price

            Get price of select token in the exchange pair
                
            Parameters
            -------
            base_tkn : float
                Base token request for price quote           
            opp_tkn : ERC20
                Denomination token of price quote                                     
        """         
        
        assert self.tkn_group.get_token(base_tkn.token_name), 'Stableswap V1: TOKEN NOT PART OF GROUP'
        
        base_tkn_index = self._get_tkn_index(base_tkn.token_name)
        opp_tkn_index = self._get_tkn_index(opp_tkn.token_name)
    
        return self.math_pool.dydx(base_tkn_index, opp_tkn_index, use_fee=fee)   
    
    def get_reserve(self, token):
        
        """ get_reserve

            Get reserve amount of select token in the pool
                
            Parameters
            -------
            token : ERC20
                ERC20 token                
        """            
        
        return self.tkn_reserves[token.token_name]    
            


        
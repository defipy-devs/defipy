# StableswapERC20Group.py
# Author: Ian Moore ( imoore@syscoin.org )
# Date: Oct 2023

import numpy as np
from decimal import Decimal
from python.prod.erc import ERC20

class StableswapERC20Group:
  
    def __init__(self) -> None:
        self.tkns = []
        self.tkn_dic = {}            
        
    def add_token(self, tkn: ERC20):
        if tkn.token_name not in self.tkn_dic:    
            self.tkns.append(tkn) 
            self.tkn_dic[tkn.token_name] = tkn
        else:
            print('ERROR: token already exists within group')

    def check_tkn(self, tkn):
        tkn_nms = self.get_names()
        return tkn.token_name in tkn_nms         
            
    def get_name(self):
        tkn_nms = self.get_names()
        return "-".join(tkn_nms)  
    
    def get_coins_str(self):
        tkn_nms = self.get_names()
        return "/".join(tkn_nms)    
 
    def get_token(self, tkn_name):
        return self.tkn_dic[tkn_name]

    def get_tokens(self):
        return self.tkns
    
    def get_names(self):
        tkn_nms = []
        for tkn in self.tkns:
            tkn_nms.append(tkn.token_name) 
        return tkn_nms    
    
    def get_dict(self):
        tkn_dict = {}
        for tkn in self.tkns:
            tkn_dict[tkn.token_name] = tkn
        return tkn_dict      
    
    def get_balances(self):
        tkn_balances = {}
        for tkn in self.tkns:
            tkn_balances[tkn.token_name] = tkn.token_total
        return tkn_balances   
            
    def get_decimals(self):
        tkn_decimals = {}
        for tkn in self.tkns:
            tkn_decimals[tkn.token_name] = tkn.token_decimal
        return tkn_decimals  
    
    def get_rates(self):
        tkn_rates = {}
        for tkn_nm in self.tkn_dic:
            tkn = self.tkn_dic[tkn_nm]
            tkn_rates[tkn.token_name] = self.rate_multiplier(tkn.token_decimal) 
        return tkn_rates 
    
    def get_decimal_amts(self):
        decimal_amts = {}
        token_decimals = self.get_decimals()
        for tkn_nm in token_decimals:
            tkn = self.get_token(tkn_nm)
            decimal_amts[tkn.token_name] = self.amt2dec(tkn.token_total, tkn.token_decimal) 
        return decimal_amts  
    
    def amt2dec(self, tkn_amt, decimal):
        return int(Decimal(str(tkn_amt))*Decimal(str(10**decimal)))    
    
    def rate_multiplier(self, decimals):
        return 10 ** (36 - decimals)    
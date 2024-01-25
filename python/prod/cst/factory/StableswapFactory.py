# StableswapFactory.py
# Author: Ian Moore ( imoore@syscoin.org )
# Date: Oct 2023

from python.prod.erc import ERC20
from python.prod.cst.exchg import StableswapExchange 
from python.prod.group import StableswapERC20Group

class StableswapFactory:
      
    def __init__(self, name: str, address: str) -> None:
        self.name = name
        self.address = address
        self.token_to_exchange = {}
        self.exchange_to_tokens = {}  
        
    def create_exchange(self, tkn_group : StableswapERC20Group, symbol: str, address : str):     
        
        if self.exchange_to_tokens.get(symbol):
            raise Exception("Exchange already created")    
            
        new_exchange = StableswapExchange(self,  tkn_group, symbol, address)  
    
        self.token_to_exchange[tkn_group.get_name()] = new_exchange
        self.exchange_to_tokens[new_exchange.name] = tkn_group.get_dict()
        
        return new_exchange  
    
    def get_exchange(self, token):
        
        return self.token_to_exchange.get(token)

    def get_token(self, exchange):       
        
        return self.exchange_to_token.get(exchange)

    def token_count(self):
 
        return len(self.token_to_exchange)    
    
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

from web3scout.event.process.retrieve_events import RetrieveEvents
from web3scout.utils.connect import ConnectW3
from web3scout.abi.abi_load import ABILoad
from web3scout.token.fetch.fetch_token import FetchToken
from .config import PriceThresholdConfig
from .data import UniswapPoolData

class PriceThresholdSwapAgent:
    def __init__(self, config: PriceThresholdConfig, verbose: bool = False):
        self.config = config
        self.abi = ABILoad(self.config.platform, self.config.abi_name)  # Load ABI here  
        self.connector = ConnectW3(self.config.provider_url)  # Web3Scout setup
        self.connector.apply()
        self.verbose = verbose
        self.lp_contract_instance = None
        self.lp_data = None
        
    def apply(self):
        self.lp_contract_instance = self._init_lp_contract()
        
        reserves = self.lp_contract_instance.functions.getReserves().call()
        token0_address = self.lp_contract_instance.functions.token0().call()
        token1_address = self.lp_contract_instance.functions.token1().call()
        reserve0 = reserves[0]; reserve1 = reserves[1]

        w3 = self.connector.get_w3()
        FetchERC20 = FetchToken(w3)
        TKN0 = FetchERC20.apply(token0_address)
        TKN1 = FetchERC20.apply(token1_address)

        self.lp_data = UniswapPoolData(TKN0, TKN1, reserves)

    def get_current_price(self, tkn1_over_tkn0 = True):

        TKN0 = self.lp_data.tkn0
        TKN1 = self.lp_data.tkn1
        reserves = self.lp_data.reserves
        reserve0 = reserves[0]; reserve1 = reserves[1]; 

        tkn0_decimal = TKN0.token_decimal
        tkn1_decimal = TKN1.token_decimal
    
        if(tkn1_over_tkn0):
            price = (reserve0 / reserve1) * (10 ** (tkn1_decimal - tkn0_decimal))
            if(self.verbose): print(f"{TKN1.token_name} Price in {TKN0.token_name}: {price}")
        else:
            price = (reserve1 / reserve0) * (10 ** (tkn0_decimal - tkn1_decimal))
            if(self.verbose): print(f"{TKN0.token_name} Price in {TKN1.token_name}: {price}")
    
        return price

    def check_condition(self, threshold = None, tkn1_over_tkn0 = True):
        self.config.threshold = self.config.threshold if threshold == None else threshold;
        self.apply()
        price = self.get_current_price(tkn1_over_tkn0)
        return price > self.config.threshold

    def get_connector(self):
        return self.connector

    def get_abi(self):
        return self.abi

    def get_w3(self):
        return self.connector.get_w3() 

    def get_contract_instance(self):
        return self.lp_contract_instance

    def get_lp_data(self):
        return self.lp_data

    def _init_lp_contract(self): 
        pair_address = self.config.pool_address
        w3 = self.get_w3()       
        abi_obj = self.get_abi()
        lp_contract_instance = abi_obj.apply(w3, pair_address)   
        return lp_contract_instance
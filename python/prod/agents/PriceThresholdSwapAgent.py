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
from web3scout.event.process.retrieve_events import RetrieveEvents
from web3scout.token.fetch.fetch_token import FetchToken
from web3scout.enums.event_type_enum import EventTypeEnum as EventType
from .config import PriceThresholdConfig
from .data import UniswapPoolData
from uniswappy import * 

class PriceThresholdSwapAgent:
    def __init__(self, config: PriceThresholdConfig, verbose: bool = False):
        self.config = config
        self.abi = ABILoad(self.config.platform, self.config.abi_name)  # Load ABI here  
        self.connector = ConnectW3(self.config.provider_url)  # Web3Scout setup
        self.connector.apply()
        self.verbose = verbose
        self.lp_contract = None
        self.lp_data = None
        self.lp_state = None
        
    def apply(self):
        self.lp_contract = self._init_lp_contract()
        
        reserves = self.lp_contract.functions.getReserves().call()
        token0_address = self.lp_contract.functions.token0().call()
        token1_address = self.lp_contract.functions.token1().call()
        reserve0 = reserves[0]; reserve1 = reserves[1]

        w3 = self.connector.get_w3()
        FetchERC20 = FetchToken(w3)
        TKN0 = FetchERC20.apply(token0_address)
        TKN1 = FetchERC20.apply(token1_address)

        self.lp_data = UniswapPoolData(TKN0, TKN1, reserves)

    def run_batch(self, tkn, events):
        start_block = events[0]['blockNumber']
        lp = self.prime_pool_state(start_block, 'user')

        """Fetch batch of Sync events and process sequentially."""
        if not events:
            print("No Sync events found in range.")
            return
        for k in events:
            reserve0 = events[k]['args']['reserve0']
            reserve1 = events[k]['args']['reserve1']
            block_num = events[k]['blockNumber']
            event_price = self.calc_price(reserve0, reserve1, tkn1_over_tkn0 = True)
            self.execute_action(lp, tkn, event_price, block_num)
    
    def prime_pool_state(self, start_block, user_nm = None):
        w3 = self.get_w3() 
        fetch_tkn = FetchToken(w3)
        
        lp_contract = self._init_lp_contract()
        tkn0_addr = lp_contract.functions.token0().call()
        tkn1_addr = lp_contract.functions.token1().call()
        total_supply = lp_contract.functions.totalSupply().call(block_identifier=start_block)
        reserves = lp_contract.functions.getReserves().call(block_identifier=start_block)
        
        # Step 2: Define tokens
        tkn0 = fetch_tkn.apply(tkn0_addr)
        tkn1 = fetch_tkn.apply(tkn1_addr)
        
        amt0 = fetch_tkn.amt_to_decimal(tkn0, reserves[0])
        amt1 = fetch_tkn.amt_to_decimal(tkn1, reserves[1])
        
        # Step 3:  Initialize factory
        factory = UniswapFactory("Pool factory", "0x2")
        
        # Step 4: Set up exchange data for V2
        exch_data = UniswapExchangeData(tkn0=tkn0, tkn1=tkn1, symbol="LP", address=self.config.pool_address)
        
        # Step 5: Deploy pool
        self.lp_state = factory.deploy(exch_data)
        
        # Step 6: Add initial liquidity
        join = Join()
        join.apply(self.lp_state, user_nm, amt0, amt1)
        self.lp_state.total_supply = total_supply # override total supply
    
        return self.lp_state

    def execute_action(self, lp, tkn, price, block_num, tkn1_over_tkn0 = True):

        tkn0 = self.lp_data.tkn0
        tkn1 = self.lp_data.tkn1
        
        """Execute swap if condition met (simulated or live)."""
        if self.check_condition(block_num = block_num, tkn1_over_tkn0 = tkn1_over_tkn0):
            try:
                out = Swap().apply(lp, tkn, "test_action", self.config.swap_amount)  
                print(f"Block {block_num}: Swapped {self.config.swap_amount} {tkn0.token_name} for {out} {tkn1.token_name}")
            except Exception as e:
                print(f"Block {block_number}: Swap failed: {e}")

    def get_token_price(self, tkn1_over_tkn0 = True, block_num = None):
        
        if(block_num == None):
            reserves = self.lp_data.reserves
        else:
            lp_contract = self._init_lp_contract()
            reserves = lp_contract.functions.getReserves().call(block_identifier=block_num)
            
        price = self.calc_price(reserves[0], reserves[1], tkn1_over_tkn0)
    
        return price

    def calc_price(self, reserve0, reserve1, tkn1_over_tkn0 = True):
        tkn0 = self.lp_data.tkn0
        tkn1 = self.lp_data.tkn1
        tkn0_decimal = tkn0.token_decimal
        tkn1_decimal = tkn1.token_decimal
        
        if(tkn1_over_tkn0):
            price = (reserve0 / reserve1) * (10 ** (tkn1_decimal - tkn0_decimal))
            if(self.verbose): print(f"{tkn1.token_name} Price in {tkn0.token_name}: {price}")
        else:
            price = (reserve1 / reserve0) * (10 ** (tkn0_decimal - tkn1_decimal))
            if(self.verbose): print(f"{tkn0.token_name} Price in {tkn1.token_name}: {price}")
                
        return price
    
    def check_condition(self, threshold = None, tkn1_over_tkn0 = True, block_num = None):
        self.config.threshold = self.config.threshold if threshold == None else threshold;
        self.apply()
        price = self.get_token_price(tkn1_over_tkn0, block_num)
        return price > self.config.threshold

    def get_connector(self):
        return self.connector

    def get_abi(self):
        return self.abi

    def get_w3(self):
        return self.connector.get_w3() 

    def get_contract_instance(self):
        return self.lp_contract

    def get_lp_data(self):
        return self.lp_data

    def _init_lp_contract(self): 
        pair_address = self.config.pool_address
        w3 = self.get_w3()       
        abi_obj = self.get_abi()
        lp_contract = abi_obj.apply(w3, pair_address)   
        return lp_contract
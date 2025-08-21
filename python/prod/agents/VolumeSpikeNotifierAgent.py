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

from pydantic import BaseModel
from web3scout.utils.connect import ConnectW3
from web3scout.abi.abi_load import ABILoad
from web3scout.event.process.retrieve_events import RetrieveEvents
from web3scout.token.fetch.fetch_token import FetchToken
from .config import VolumeSpikeConfig
from .data import UniswapPoolData
from uniswappy import * 
from web3 import Web3

class VolumeSpikeNotifierAgent:
    def __init__(self, config: VolumeSpikeConfig, verbose: bool = False):
        self.config = config
        self.abi = ABILoad(self.config.platform, self.config.abi_name)  # Load ABI here  
        self.connector = ConnectW3(self.config.provider_url)  # Web3Scout setup
        self.connector.apply()
        self.verbose = verbose
        self.pool_volume = None
        self.lp_contract = None
        self.lp_data = None
        self.lp_state = None

    def init(self):
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

    def prime_mock_pool(self, start_block, user_nm = None):
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

    def update_mock_pool(self, lp, cur_block):
        w3 = self.get_w3() 
        fetch_tkn = FetchToken(w3)
        
        lp_contract = self._init_lp_contract()
        tkn0_addr = lp_contract.functions.token0().call()
        tkn1_addr = lp_contract.functions.token1().call()
        total_supply = lp_contract.functions.totalSupply().call(block_identifier=int(cur_block))
        reserves = lp_contract.functions.getReserves().call(block_identifier=int(cur_block))
        
        tkn0 = self.get_lp_data().tkn0
        tkn1 = self.get_lp_data().tkn1
        amt0 = fetch_tkn.amt_to_decimal(tkn0, reserves[0])
        amt1 = fetch_tkn.amt_to_decimal(tkn1, reserves[1])
        
        prev_total_supply = lp.total_supply
        lp.reserve0 = lp.convert_to_machine(amt0)      # override reserve0
        lp.reserve1 = lp.convert_to_machine(amt1)      # override reserve1
        lp.total_supply = total_supply                 # override total supply
        lp.last_liquidity_deposit = abs(prev_total_supply - lp.total_supply)
        
        return lp

    def run_batch(self, lp, tkn, user_nm, events: dict):
        """Process batched Sync events to check TVL and trigger exits."""
        if not events:
            print("No Sync events found in range.")
            return
        for k in events:
            block_num = events[k]['blockNumber']
            self.apply(lp, tkn, user_nm, block_num)

    def apply(self, lp, tkn, user_nm, block_num):
        """Execute liquidity exit if condition met."""
        if self.check_condition(lp, tkn, self.config.volume_threshold, block_num):
            vol = self.pool_volume
            print(f"Block {block_num}: Volume ({tkn.token_name}) = {vol}, outside threshold {self.config.volume_threshold}")
            return vol
        else:
            print(f"Block {block_num}: Volume threshold condition met for {lp.name} LP")
            return None

    def take_mock_position(self, lp, tkn, user_nm, amt):
        SwapDeposit().apply(lp, tkn, user_nm, amt)
        self.mock_lp_pos_amt = lp.get_last_liquidity_deposit()
        return self.mock_lp_pos_amt

    def withdraw_mock_position(self, lp, tkn, user_nm, lp_amt = None):
        assert self.mock_lp_pos_amt != None, 'TVLBasedLiquidityExitAgent: MOCK_POSITION_UNAVAILABLE' 
        lp_amt = self.mock_lp_pos_amt if lp_amt == None else lp_amt
        tkn_amt = LPQuote(False).get_amount_from_lp(lp, tkn0, lp_amt)
        amount_out = WithdrawSwap().apply(lp, tkn0, user_nm, tkn_amt)
        return amount_out

    def get_pool_volume(self, lp, tkn, block_num):
        """Calculate TVL from reserves (sum in USD, assuming base_token normalization)."""

        tkn0 = self.get_lp_data().tkn0
        tkn1 = self.get_lp_data().tkn1
        prev_tkn0 = lp.get_reserve(tkn0)
        prev_tkn1 = lp.get_reserve(tkn1)

        lp = self.update_mock_pool(lp, block_num)
        
        dtkn0 = abs(lp.get_reserve(tkn0) - prev_tkn0)
        dtkn1 = abs(lp.get_reserve(tkn1) - prev_tkn1)

        if(tkn.token_name == tkn0.token_name):
            volume = dtkn0 + LPQuote().get_amount(lp, tkn1, dtkn1)  
        elif(tkn.token_name == tkn1.token_name):
            volume = dtkn1 + LPQuote().get_amount(lp, tkn0, dtkn0)
        
        self.pool_volume = volume
        return volume

    def check_condition(self, lp, tkn, threshold, block_num = None):
        """Check if TVL is below threshold."""
        block_num = self.get_w3().eth.block_number if block_num == None else block_num
        volume = self.get_pool_volume(lp, tkn, block_num)
        return volume > threshold

    def _init_lp_contract(self): 
        pair_address = self.config.pool_address
        w3 = self.get_w3()       
        abi_obj = self.get_abi()
        lp_contract = abi_obj.apply(w3, pair_address)   
        return lp_contract
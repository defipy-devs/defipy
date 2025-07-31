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

class PriceThresholdConfig(BaseModel):  
    threshold: float  # e.g., 3000.0 (price above which to swap)
    swap_amount: float  # e.g., 1.0 (swap amount if threshold met)
    pool_address: str  # Uniswap V2 pool
    provider_url: str  # e.g., Infura for Web3Scout
    abi_name: str  # e.g., 'UniswapV2Pair' (new field for ABI identifier)
    platform: str  # e.g., 'UNI' or 'SUSHI' for the protocoll
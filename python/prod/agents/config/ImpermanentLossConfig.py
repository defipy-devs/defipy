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

class ImpermanentLossConfig(BaseModel):
    il_threshold: float  # Impermanent loss threshold percentage (e.g., 5.0 for 5%)
    pool_address: str       # Uniswap V2 pool address
    provider_url: str       # Web3 provider URL (e.g., Infura)
    abi_name: str  # e.g., 'UniswapV2Pair' (new field for ABI identifier)
    platform: str  # e.g., 'UNI' or 'SUSHI' for the protocoll
    user_position: float    # Initial mock position amount for off-chain testing
    exit_percentage: float  # Percentage of position to exit upon trigger (e.g., 1.0 for 100%)
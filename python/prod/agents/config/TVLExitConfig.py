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

class TVLExitConfig(BaseModel):
    tvl_threshold: float  # e.g., 1000000.0 (minimum TVL in USD)
    exit_percentage: float  # e.g., 1.0 (full exit) or 0.5 (half)
    pool_address: str  # Pool contract address
    provider_url: str  # Web3 provider URL
    abi_name: str  # e.g., 'UniswapV2Pair' (new field for ABI identifier)
    platform: str  # e.g., 'UNI' or 'SUSHI' for the protocoll
    user_position: float  # User's LP shares or amount
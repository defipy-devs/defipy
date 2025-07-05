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

import subprocess

FORGE_CMD = 'forge'
SCRIPT_CMD = 'script'
SILENT_OPT = '--silent'
SKIP_SIM_OPT = '--skip-simulation'
SIG_OPT = '--sig'
SIG_OPT = '--sig'
RPC_OPT = '--rpc-url'
BROADCAST_OPT = '--broadcast'

class ExecuteScript():

    def __init__(self, test_directory):
        self.test_directory = test_directory
        pass

    def apply(self, script_path, rpc_url, args = [], verbose = True, skip_sim = True):
        shell_cmd = self._exe_cmd(script_path, rpc_url, args=args, verbose=verbose, skip_sim=skip_sim)
        p = subprocess.Popen(shell_cmd, cwd=self.test_directory)
        p.wait()
          
    def _exe_cmd(self, script_path, rpc_url, verbose = True, skip_sim = True, args = []):
        silent_cmd = SILENT_OPT if not verbose else ''
        skip_sim_cmd = SKIP_SIM_OPT if skip_sim else ''
        deploy_sig = [] if len(args) == 0 else [SIG_OPT]
        deploy_arg_type = [] if len(args) == 0 else ['run('+','.join('uint256' for e in args)+')']
        deploy_args = [] if len(args) == 0 else [str(e) for e in args]
    
        shell_cmd1 = [FORGE_CMD, SCRIPT_CMD, script_path]
        shell_cmd2 = deploy_args + deploy_sig + deploy_arg_type
        shell_cmd3 = [ '--ignored-error-codes', '2072', 
                    '--ignored-error-codes', '6321', 
                    '--ignored-error-codes', '5667', 
                    '--ignored-error-codes', '5574', 
                     '--ignored-error-codes', '2018']
        shell_cmd4 = [RPC_OPT, rpc_url, BROADCAST_OPT,  silent_cmd, skip_sim_cmd]
        shell_cmd = shell_cmd1 + shell_cmd2 + shell_cmd3 + shell_cmd4 
        return shell_cmd
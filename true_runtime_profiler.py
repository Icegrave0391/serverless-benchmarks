#!/usr/bin/env python3
"""
True Runtime Profiler - Profile Python serverless functions with syscall tracing
Focus on profiling function execution within current runtime (Python already loaded)
"""

import os
import sys
import subprocess
import json
import time
import importlib.util
from pathlib import Path
import signal

class TrueRuntimeProfiler:
    def __init__(self):
        self.functions = self._discover_functions()
        # Correct input data for different functions
        self.correct_inputs = {
            # Only this 110. works for now... Not a best way to set up the environment.
            '110.dynamic-html': {'username': 'testuser', 'random_len': 10},
            '130.crud-api': {'action': 'get', 'id': '1'},
            '210.thumbnailer': {'image': 'test.jpg', 'size': 100},
            '220.video-processing': {'video': 'test.mp4'},
            '311.compression': {'text': 'Hello World'},
            '411.image-recognition': {'image': 'test.jpg'},
            '503.graph-bfs': {'size': 10},
            '501.graph-pagerank': {'size': 10},
            '504.dna-visualisation': {'sequence': 'ATCGATCG'},
            '502.graph-mst': {'size': 10},
            '020.network-benchmark': {'port': 8080},
            '030.clock-synchronization': {'time': '12:00:00'},
            '040.server-reply': {'message': 'hello'},
            '010.sleep': {'sleep_time': 1},
            '120.uploader': {'file': 'test.txt', 'content': 'hello world'}
        }
    
    def _discover_functions(self):
        """Discover all Python functions in the benchmarks directory"""
        functions = []
        benchmarks_dir = Path("benchmarks")
        
        for function_py in benchmarks_dir.rglob("*/python/function.py"):
            parts = function_py.parts
            if len(parts) >= 4:
                category = parts[1]
                name = parts[2]
                functions.append({
                    'name': name,
                    'category': category,
                    'function_path': str(function_py),
                    'input_path': str(function_py.parent / 'input.py')
                })
        
        return functions
    
    def _get_input_for_function(self, function_name):
        """Get correct input data for a specific function"""
        return self.correct_inputs.get(function_name, {'data': 'test'})
    
    def profile_function_in_runtime(self, function_info, summary=True):
        """Profile function loading and execution within current runtime (Python already loaded)"""
        function_path = function_info['function_path']
        function_name = function_info['name']
        input_data = self._get_input_for_function(function_name)
        
        mode_str = "summary" if summary else "full"
        print(f"=== Profiling {function_name} in current runtime ({mode_str}) ===")
        print(f"Function path: {function_path}")
        print(f"Input data: {input_data}")
        
        # Get current process PID
        current_pid = os.getpid()
        
        # Create output file for strace results with different names
        if summary:
            strace_file = f"runtime_summary_{function_name}.txt"
            strace_cmd = ['strace', '-c', '-p', str(current_pid), '-o', strace_file]
        else:
            strace_file = f"runtime_full_{function_name}.txt"
            strace_cmd = ['strace', '-p', str(current_pid), '-o', strace_file]
        
        strace_proc = None
        try:
            # Start strace
            strace_proc = subprocess.Popen(
                strace_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for strace to attach to the process
            time.sleep(1)
            
            # === Start of profiled section: function loading and execution ===
            function_result = None
            error_msg = None
            
            try:
                # Load function module
                spec = importlib.util.spec_from_file_location("func_module", function_path)
                func_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(func_module)
                
                # Execute function
                function_result = func_module.handler(input_data)
                    
            except Exception as e:
                error_msg = str(e)
            
            # === End of profiled section ===
            
            # Stop strace process
            if strace_proc:
                strace_proc.send_signal(signal.SIGINT)
                strace_proc.wait(timeout=10)
            
            print(f"Runtime strace file saved: {strace_file}")
            
            return {
                'function_name': function_name,
                'profiling_mode': f'runtime_{mode_str}',
                'success': True,
                'function_result': function_result,
                'error': error_msg,
                'input_data': input_data,
                'strace_file': strace_file
            }
            
        except Exception as e:
            return {
                'function_name': function_name,
                'profiling_mode': f'runtime_{mode_str}',
                'success': False,
                'error': str(e),
                'input_data': input_data
            }
        finally:
            # Cleanup
            if strace_proc and strace_proc.poll() is None:
                try:
                    strace_proc.terminate()
                    strace_proc.wait(timeout=5)
                except:
                    pass

    def profile_full_python(self, function_info):
        """Profile entire Python execution including startup and function execution"""
        import tempfile
        
        function_path = function_info['function_path']
        function_name = function_info['name']
        input_data = self._get_input_for_function(function_name)
        
        print(f"=== Profiling {function_name} with full Python execution ===")
        print(f"Function path: {function_path}")
        print(f"Input data: {input_data}")
        
        # Create output files for strace results
        strace_summary_file = f"fullpython_summary_{function_name}.txt"
        strace_full_file = f"fullpython_full_{function_name}.txt"
        
        # Create a temporary Python script to execute the function
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_script:
            script_content = f'''
import importlib.util
import json
import sys
from pathlib import Path

# Function execution script
function_path = "{function_path}"
input_data = {repr(input_data)}

try:
    # Load function module
    spec = importlib.util.spec_from_file_location("func_module", function_path)
    func_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(func_module)
    
    # Execute function
    result = func_module.handler(input_data)
    
    # Print result without extra output during strace
    print(repr(result))
        
except Exception as e:
    print(f"ERROR: {{e}}")
    sys.exit(1)
'''
            temp_script.write(script_content)
            temp_script_path = temp_script.name
        
        try:
            # Run strace for summary (with -c flag)
            strace_summary_cmd = ['strace', '-c', '-f', '-o', strace_summary_file, 'python3', temp_script_path]
            
            result_summary = subprocess.run(
                strace_summary_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Run strace for full trace (without -c flag)
            strace_full_cmd = ['strace', '-f', '-o', strace_full_file, 'python3', temp_script_path]
            
            result_full = subprocess.run(
                strace_full_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Parse function output from summary run (both should have same output)
            function_result = None
            error_msg = None
            
            if result_summary.returncode == 0:
                try:
                    # The output should be the repr() of the result
                    output_line = result_summary.stdout.strip()
                    if output_line and not output_line.startswith('ERROR:'):
                        function_result = eval(output_line)  # Safe since we control the output
                except:
                    pass
            else:
                if result_summary.stdout and result_summary.stdout.startswith('ERROR:'):
                    error_msg = result_summary.stdout.split('ERROR:', 1)[1].strip()
                else:
                    error_msg = f"Process failed with exit code {result_summary.returncode}"
                    if result_summary.stderr:
                        error_msg += f": {result_summary.stderr}"
            
            print(f"Full Python strace files saved:")
            print(f"  Summary: {strace_summary_file}")
            print(f"  Full trace: {strace_full_file}")
            
            return {
                'function_name': function_name,
                'profiling_mode': 'full_python',
                'success': True,
                'function_result': function_result,
                'error': error_msg,
                'input_data': input_data,
                'strace_summary_file': strace_summary_file,
                'strace_full_file': strace_full_file,
                'stdout': result_summary.stdout,
                'stderr': result_summary.stderr
            }
            
        except subprocess.TimeoutExpired:
            return {
                'function_name': function_name,
                'profiling_mode': 'full_python',
                'success': False,
                'error': 'Full Python execution timed out',
                'input_data': input_data
            }
        except Exception as e:
            return {
                'function_name': function_name,
                'profiling_mode': 'full_python',
                'success': False,
                'error': str(e),
                'input_data': input_data
            }
        finally:
            # Cleanup temporary script
            try:
                os.unlink(temp_script_path)
            except:
                pass
    
def main():
    """Main function demonstrating both profiling methods"""
    profiler = TrueRuntimeProfiler()
    
    print("=== True Runtime Profiler - Dual Mode Demo ===")
    print("This tool provides two profiling modes:")
    print("1. Runtime-only: Profile function loading/execution (Python runtime already loaded)")
    print("2. Full Python: Profile entire Python execution including runtime startup + function loading/exec")
    print()
    
    # Find target function for testing
    target_func = None
    for func in profiler.functions:
        if '110.dynamic-html' in func['name']:
            target_func = func
            break
    
    if target_func:
        print(f"Testing with function: {target_func['name']}")
        
        # Profile with runtime-only method (summary)
        print("\n1a. Profiling with runtime-only method (summary)...")
        runtime_summary_result = profiler.profile_function_in_runtime(target_func, summary=True)
        
        # print("\n" + "="*60)
        
        # Profile with runtime-only method (full)
        print("\n1b. Profiling with runtime-only method (full)...")
        runtime_full_result = profiler.profile_function_in_runtime(target_func, summary=False)
        
        print("\n" + "="*60)
        
        # Profile with full Python method
        print("\n2. Profiling with full Python method...")
        fullpython_result = profiler.profile_full_python(target_func)
        
        print("\n" + "="*60)
        
        # Show results
        print("\n=== Final Results ===")
        
        # if runtime_summary_result['success']:
        #     print(f"Runtime-only profiling (summary):")
        #     print(f"  Function executed: {'✓' if runtime_summary_result['function_result'] is not None else '✗'}")
        #     if runtime_summary_result['function_result'] is not None:
        #         print(f"  Function result: {runtime_summary_result['function_result']}")
        #     if runtime_summary_result['error']:
        #         print(f"  Function error: {runtime_summary_result['error']}")
        
        if runtime_full_result['success']:
            print(f"\nRuntime-only profiling (full):")
            print(f"  Function executed: {'✓' if runtime_full_result['function_result'] is not None else '✗'}")
            if runtime_full_result['function_result'] is not None:
                print(f"  Function result: {runtime_full_result['function_result']}")
            if runtime_full_result['error']:
                print(f"  Function error: {runtime_full_result['error']}")
        
        if fullpython_result['success']:
            print(f"\nFull Python profiling:")
            print(f"  Function executed: {'✓' if fullpython_result['function_result'] is not None else '✗'}")
            if fullpython_result['function_result'] is not None:
                print(f"  Function result: {fullpython_result['function_result']}")
            if fullpython_result['error']:
                print(f"  Function error: {fullpython_result['error']}")
        
    else:
        print("No suitable test function found")
        print("Available functions:")
        for func in profiler.functions[:5]:
            print(f"  - {func['name']} ({func['category']})")

if __name__ == '__main__':
    main()

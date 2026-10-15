import docker
import tempfile
import os
from docker.errors import ContainerError, APIError

def execute_cpp_submission(source_code: str, input_data: str = "") -> dict:
    """
    Compiles and executes C++ code inside an isolated Docker sandbox.
    """
    client = docker.from_env()
    # Using a standard GCC image. 
    # Note for M4 Mac: This will pull the arm64 image natively.
    DOCKER_IMAGE = "gcc:11" 

    # Create a temporary directory on the host to hold source, input, and binary
    with tempfile.TemporaryDirectory() as temp_dir:
        source_path = os.path.join(temp_dir, "main.cpp")
        input_path = os.path.join(temp_dir, "input.txt")
        
        with open(source_path, "w") as f:
            f.write(source_code)
        with open(input_path, "w") as f:
            f.write(input_data)

        # Map the host temp directory to /usr/src/app inside the container
        volumes = {
            temp_dir: {'bind': '/usr/src/app', 'mode': 'rw'}
        }

        # ==========================================
        # PHASE 1: COMPILATION
        # ==========================================
        try:
            client.containers.run(
                image=DOCKER_IMAGE,
                command="g++ -O2 -std=c++17 main.cpp -o main",
                volumes=volumes,
                working_dir="/usr/src/app",
                remove=True, # Automatically remove container after it exits
                network_disabled=True # No internet access during compilation
            )
        except ContainerError as e:
            # Non-zero exit code during compilation means Compilation Error
            return {
                "status": "Compilation Error",
                "output": e.stderr.decode('utf-8', errors='ignore') if e.stderr else "Unknown Compilation Error"
            }
        except APIError as e:
            return {"status": "System Error", "output": f"Docker API Error: {str(e)}"}

        # ==========================================
        # PHASE 2: EXECUTION
        # ==========================================
        try:
            # We use the Linux `timeout` utility inside the container to enforce the 1-second wall-clock time limit.
            # Standard input is redirected from our input.txt file.
            run_cmd = 'sh -c "timeout 1s ./main < input.txt"'

            logs = client.containers.run(
                image=DOCKER_IMAGE,
                command=run_cmd,
                volumes=volumes,
                working_dir="/usr/src/app",
                remove=True,
                mem_limit="256m",           # 256MB memory cap
                memswap_limit="256m",       # Set equal to mem_limit to completely disable swap
                network_disabled=True,      # Strict isolation: no network
                pids_limit=64,              # Prevent fork bombs
                cap_drop=["ALL"],           # Drop all Linux capabilities (root inside container is neutered)
                read_only=True,             # Prevent writing to the container's root file system
                stdout=True,
                stderr=True
            )
            
            return {
                "status": "Accepted", 
                "output": logs.decode('utf-8', errors='ignore').strip()
            }

        except ContainerError as e:
            # Handle specific failure exit codes
            exit_code = e.exit_status
            output = e.stderr.decode('utf-8', errors='ignore') if e.stderr else ""

            if exit_code == 124:
                return {"status": "Time Limit Exceeded", "output": ""}
            elif exit_code == 137:
                # 137 typically means the Docker daemon killed the process due to OOM
                return {"status": "Memory Limit Exceeded", "output": ""}
            elif exit_code == 139:
                return {"status": "Runtime Error (Segmentation Fault)", "output": output}
            else:
                return {"status": f"Runtime Error (Exit Code {exit_code})", "output": output}
        except Exception as e:
            return {"status": "System Error", "output": str(e)}

# --- Test the Sandbox ---
if __name__ == "__main__":
    # Test 1: Accepted
    cpp_code_success = """
    #include <iostream>
    int main() {
        int n;
        std::cin >> n;
        std::cout << "Square is: " << n * n << std::endl;
        return 0;
    }
    """
    print("Test 1:", execute_cpp_submission(cpp_code_success, "5"))

    # Test 2: Time Limit Exceeded (Infinite Loop)
    cpp_code_tle = """
    int main() {
        while(true) {}
        return 0;
    }
    """
    print("Test 2:", execute_cpp_submission(cpp_code_tle))

    # Test 3: Memory Limit Exceeded (Array allocation)
    cpp_code_mle = """
    #include <vector>
    int main() {
        // Attempting to allocate ~400MB
        std::vector<int> big_vector(100000000, 1);
        return 0;
    }
    """
    print("Test 3:", execute_cpp_submission(cpp_code_mle))
#!/usr/bin/env python3
"""
Script to run the comprehensive integration tests for the Apex Legends Leaderboard QoL features.

This script will:
1. Start the test server
2. Wait for it to be ready
3. Run all integration tests
4. Generate a comprehensive report
"""

import subprocess
import time
import sys
import os
import requests
from threading import Thread
import signal

def start_test_server():
    """Start the test server in a subprocess"""
    print("Starting test server...")
    try:
        # Start the server
        server_process = subprocess.Popen(
            [sys.executable, "test_server.py"],
            cwd=os.path.dirname(__file__),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        return server_process
    except Exception as e:
        print(f"Failed to start test server: {e}")
        return None

def wait_for_server(max_wait=30):
    """Wait for the server to be ready"""
    print("Waiting for server to be ready...")
    
    for i in range(max_wait):
        try:
            response = requests.get("http://localhost:8080", timeout=2)
            if response.status_code == 200:
                print("✅ Server is ready!")
                return True
        except:
            pass
        
        print(f"  Waiting... ({i+1}/{max_wait})")
        time.sleep(1)
    
    print("❌ Server failed to start in time")
    return False

def run_integration_tests():
    """Run the integration test suite"""
    print("\n" + "="*60)
    print("RUNNING INTEGRATION TESTS")
    print("="*60)
    
    try:
        # Run the integration tests
        result = subprocess.run(
            [sys.executable, "integration_test.py"],
            cwd=os.path.dirname(__file__),
            text=True,
            capture_output=True
        )
        
        # Print the output
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"Failed to run integration tests: {e}")
        return False

def main():
    """Main function"""
    print("Apex Legends Leaderboard - QoL Integration Testing")
    print("="*60)
    
    server_process = None
    
    try:
        # Start the test server
        server_process = start_test_server()
        if not server_process:
            print("❌ Failed to start test server")
            return False
        
        # Wait for server to be ready
        if not wait_for_server():
            print("❌ Server not responding")
            return False
        
        # Run integration tests
        success = run_integration_tests()
        
        if success:
            print("\n🎉 ALL TESTS PASSED!")
            print("✅ QoL features are working correctly")
            print("✅ No performance issues detected")
            print("✅ All integrations successful")
        else:
            print("\n❌ SOME TESTS FAILED")
            print("Please check the detailed report for issues")
        
        return success
        
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        return False
        
    finally:
        # Clean up - terminate the server
        if server_process:
            try:
                print("\nStopping test server...")
                server_process.terminate()
                server_process.wait(timeout=5)
                print("✅ Test server stopped")
            except:
                try:
                    server_process.kill()
                    print("🔪 Test server force killed")
                except:
                    print("⚠️  Could not stop test server")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
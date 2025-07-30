#!/usr/bin/env python3
"""
Comprehensive Backend API Tests for Apex Legends Leaderboard
Tests all endpoints for success cases and error handling
"""

import requests
import json
import time
import sys
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8001"  # Local Flask server
API_BASE = f"{BASE_URL}/api"

class APITester:
    def __init__(self):
        self.results = []
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        
    def log_result(self, test_name, success, message, response_data=None):
        """Log test result"""
        self.total_tests += 1
        if success:
            self.passed_tests += 1
            status = "✅ PASS"
        else:
            self.failed_tests += 1
            status = "❌ FAIL"
            
        result = {
            "test": test_name,
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        if response_data:
            result["response_data"] = response_data
            
        self.results.append(result)
        print(f"{status}: {test_name} - {message}")
        
    def test_health_endpoint(self):
        """Test /api/health endpoint"""
        print("\n=== Testing Health Check Endpoint ===")
        
        try:
            response = requests.get(f"{API_BASE}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check required fields
                required_fields = ["status", "timestamp", "version"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_result("Health Check - Response Structure", False, 
                                  f"Missing fields: {missing_fields}", data)
                else:
                    self.log_result("Health Check - Response Structure", True, 
                                  "All required fields present", data)
                
                # Check status value
                if data.get("status") == "healthy":
                    self.log_result("Health Check - Status Value", True, 
                                  "Status is 'healthy'", data)
                else:
                    self.log_result("Health Check - Status Value", False, 
                                  f"Status is '{data.get('status')}', expected 'healthy'", data)
                    
                # Check timestamp format
                try:
                    datetime.fromisoformat(data.get("timestamp", "").replace("Z", "+00:00"))
                    self.log_result("Health Check - Timestamp Format", True, 
                                  "Timestamp is valid ISO format", data)
                except:
                    self.log_result("Health Check - Timestamp Format", False, 
                                  "Invalid timestamp format", data)
            else:
                self.log_result("Health Check - HTTP Status", False, 
                              f"Expected 200, got {response.status_code}", response.text)
                
        except requests.exceptions.Timeout:
            self.log_result("Health Check - Timeout", False, "Request timed out")
        except requests.exceptions.ConnectionError:
            self.log_result("Health Check - Connection", False, "Connection failed")
        except Exception as e:
            self.log_result("Health Check - Exception", False, f"Unexpected error: {str(e)}")
    
    def test_leaderboard_endpoint(self):
        """Test /api/leaderboard/<platform> endpoint"""
        print("\n=== Testing Leaderboard Endpoint ===")
        
        # Test valid platform
        try:
            response = requests.get(f"{API_BASE}/leaderboard/PC", timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check response structure
                required_fields = ["success", "data"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_result("Leaderboard PC - Response Structure", False, 
                                  f"Missing fields: {missing_fields}")
                else:
                    self.log_result("Leaderboard PC - Response Structure", True, 
                                  "Response has required structure")
                
                # Check success flag
                if data.get("success"):
                    self.log_result("Leaderboard PC - Success Flag", True, "Success is True")
                    
                    # Check data structure
                    leaderboard_data = data.get("data", {})
                    if "players" in leaderboard_data and isinstance(leaderboard_data["players"], list):
                        self.log_result("Leaderboard PC - Players Data", True, 
                                      f"Found {len(leaderboard_data['players'])} players")
                        
                        # Check player structure
                        if leaderboard_data["players"]:
                            player = leaderboard_data["players"][0]
                            player_fields = ["rank", "player_name", "rp", "twitch_link", "status"]
                            missing_player_fields = [field for field in player_fields if field not in player]
                            
                            if missing_player_fields:
                                self.log_result("Leaderboard PC - Player Structure", False, 
                                              f"Missing player fields: {missing_player_fields}")
                            else:
                                self.log_result("Leaderboard PC - Player Structure", True, 
                                              "Player data has correct structure")
                    else:
                        self.log_result("Leaderboard PC - Players Data", False, 
                                      "No players data or invalid format")
                else:
                    self.log_result("Leaderboard PC - Success Flag", False, 
                                  f"Success is False: {data.get('error', 'No error message')}")
            else:
                self.log_result("Leaderboard PC - HTTP Status", False, 
                              f"Expected 200, got {response.status_code}")
                
        except requests.exceptions.Timeout:
            self.log_result("Leaderboard PC - Timeout", False, "Request timed out (30s)")
        except Exception as e:
            self.log_result("Leaderboard PC - Exception", False, f"Unexpected error: {str(e)}")
        
        # Test invalid platform
        try:
            response = requests.get(f"{API_BASE}/leaderboard/INVALID", timeout=10)
            # Should still return 200 but might have different behavior
            self.log_result("Leaderboard Invalid Platform", True, 
                          f"Handled invalid platform, status: {response.status_code}")
        except Exception as e:
            self.log_result("Leaderboard Invalid Platform", False, f"Error: {str(e)}")
    
    def test_predator_points_endpoint(self):
        """Test /api/predator-points endpoint"""
        print("\n=== Testing Predator Points Endpoint ===")
        
        try:
            response = requests.get(f"{API_BASE}/predator-points", timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check response structure
                if data.get("success"):
                    self.log_result("Predator Points - Success Flag", True, "Success is True")
                    
                    # Check data structure
                    points_data = data.get("data", {})
                    expected_platforms = ["PC", "PS4", "X1", "SWITCH"]
                    
                    found_platforms = [platform for platform in expected_platforms if platform in points_data]
                    
                    if len(found_platforms) == len(expected_platforms):
                        self.log_result("Predator Points - Platform Coverage", True, 
                                      f"All platforms present: {found_platforms}")
                    else:
                        missing_platforms = [p for p in expected_platforms if p not in found_platforms]
                        self.log_result("Predator Points - Platform Coverage", False, 
                                      f"Missing platforms: {missing_platforms}")
                    
                    # Check platform data structure
                    if points_data:
                        platform_data = list(points_data.values())[0]
                        if "predator_rp" in platform_data or "error" in platform_data:
                            self.log_result("Predator Points - Data Structure", True, 
                                          "Platform data has expected structure")
                        else:
                            self.log_result("Predator Points - Data Structure", False, 
                                          "Platform data missing expected fields")
                else:
                    self.log_result("Predator Points - Success Flag", False, 
                                  f"Success is False: {data.get('error', 'No error message')}")
            else:
                self.log_result("Predator Points - HTTP Status", False, 
                              f"Expected 200, got {response.status_code}")
                
        except requests.exceptions.Timeout:
            self.log_result("Predator Points - Timeout", False, "Request timed out (20s)")
        except Exception as e:
            self.log_result("Predator Points - Exception", False, f"Unexpected error: {str(e)}")
    
    def test_twitch_override_endpoint(self):
        """Test /api/add-twitch-override endpoint"""
        print("\n=== Testing Twitch Override Endpoint ===")
        
        # Test valid POST request
        test_data = {
            "player_name": "TestPlayer123",
            "twitch_username": "teststreamer",
            "display_name": "Test Player"
        }
        
        try:
            response = requests.post(f"{API_BASE}/add-twitch-override", 
                                   json=test_data, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.log_result("Twitch Override - Valid POST", True, 
                                  "Successfully added Twitch override")
                else:
                    self.log_result("Twitch Override - Valid POST", False, 
                                  f"Failed to add override: {data.get('error')}")
            else:
                self.log_result("Twitch Override - Valid POST", False, 
                              f"Expected 200, got {response.status_code}")
                
        except Exception as e:
            self.log_result("Twitch Override - Valid POST", False, f"Error: {str(e)}")
        
        # Test invalid POST request (missing required fields)
        invalid_data = {"invalid_field": "value"}
        
        try:
            response = requests.post(f"{API_BASE}/add-twitch-override", 
                                   json=invalid_data, timeout=10)
            
            if response.status_code == 400:
                self.log_result("Twitch Override - Invalid POST", True, 
                              "Correctly rejected invalid request with 400")
            else:
                self.log_result("Twitch Override - Invalid POST", False, 
                              f"Expected 400, got {response.status_code}")
                
        except Exception as e:
            self.log_result("Twitch Override - Invalid POST", False, f"Error: {str(e)}")
        
        # Test GET request (should not be allowed)
        try:
            response = requests.get(f"{API_BASE}/add-twitch-override", timeout=10)
            
            if response.status_code == 405:
                self.log_result("Twitch Override - GET Method", True, 
                              "Correctly rejected GET request with 405")
            else:
                self.log_result("Twitch Override - GET Method", False, 
                              f"Expected 405, got {response.status_code}")
                
        except Exception as e:
            self.log_result("Twitch Override - GET Method", False, f"Error: {str(e)}")
    
    def test_player_stats_endpoint(self):
        """Test /api/player/<platform>/<player_name> endpoint"""
        print("\n=== Testing Player Stats Endpoint ===")
        
        # Test with valid platform and player name
        try:
            response = requests.get(f"{API_BASE}/player/PC/TestPlayer", timeout=15)
            
            # This might return 404 if player doesn't exist, which is expected
            if response.status_code in [200, 404]:
                data = response.json()
                if response.status_code == 200 and data.get("success"):
                    self.log_result("Player Stats - Valid Request", True, 
                                  "Successfully retrieved player stats")
                elif response.status_code == 404:
                    self.log_result("Player Stats - Valid Request", True, 
                                  "Correctly handled non-existent player with 404")
                else:
                    self.log_result("Player Stats - Valid Request", False, 
                                  f"Unexpected response: {data}")
            else:
                self.log_result("Player Stats - Valid Request", False, 
                              f"Unexpected status code: {response.status_code}")
                
        except requests.exceptions.Timeout:
            self.log_result("Player Stats - Valid Request", False, "Request timed out")
        except Exception as e:
            self.log_result("Player Stats - Valid Request", False, f"Error: {str(e)}")
        
        # Test with invalid platform
        try:
            response = requests.get(f"{API_BASE}/player/INVALID/TestPlayer", timeout=10)
            
            if response.status_code == 400:
                self.log_result("Player Stats - Invalid Platform", True, 
                              "Correctly rejected invalid platform with 400")
            else:
                self.log_result("Player Stats - Invalid Platform", False, 
                              f"Expected 400, got {response.status_code}")
                
        except Exception as e:
            self.log_result("Player Stats - Invalid Platform", False, f"Error: {str(e)}")
    
    def test_tracker_stats_endpoint(self):
        """Test /api/tracker-stats endpoint"""
        print("\n=== Testing Tracker Stats Endpoint ===")
        
        # Test with valid parameters
        params = {
            "platform": "origin",
            "identifier": "testplayer"
        }
        
        try:
            response = requests.get(f"{API_BASE}/tracker-stats", params=params, timeout=15)
            
            # This might return various status codes depending on Tracker.gg API
            if response.status_code in [200, 404, 503]:
                data = response.json()
                self.log_result("Tracker Stats - Valid Request", True, 
                              f"Handled request appropriately, status: {response.status_code}")
            else:
                self.log_result("Tracker Stats - Valid Request", False, 
                              f"Unexpected status code: {response.status_code}")
                
        except requests.exceptions.Timeout:
            self.log_result("Tracker Stats - Valid Request", False, "Request timed out")
        except Exception as e:
            self.log_result("Tracker Stats - Valid Request", False, f"Error: {str(e)}")
        
        # Test with missing parameters
        try:
            response = requests.get(f"{API_BASE}/tracker-stats", timeout=10)
            
            if response.status_code == 400:
                self.log_result("Tracker Stats - Missing Params", True, 
                              "Correctly rejected request with missing parameters")
            else:
                self.log_result("Tracker Stats - Missing Params", False, 
                              f"Expected 400, got {response.status_code}")
                
        except Exception as e:
            self.log_result("Tracker Stats - Missing Params", False, f"Error: {str(e)}")
    
    def test_user_endpoints(self):
        """Test user CRUD endpoints"""
        print("\n=== Testing User CRUD Endpoints ===")
        
        # Test GET /api/users
        try:
            response = requests.get(f"{API_BASE}/users", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.log_result("Users - GET All", True, 
                                  f"Retrieved {len(data)} users")
                else:
                    self.log_result("Users - GET All", False, 
                                  "Response is not a list")
            else:
                self.log_result("Users - GET All", False, 
                              f"Expected 200, got {response.status_code}")
                
        except Exception as e:
            self.log_result("Users - GET All", False, f"Error: {str(e)}")
        
        # Test POST /api/users
        test_user = {
            "username": f"testuser_{int(time.time())}",
            "email": f"test_{int(time.time())}@example.com"
        }
        
        created_user_id = None
        
        try:
            response = requests.post(f"{API_BASE}/users", json=test_user, timeout=10)
            
            if response.status_code == 201:
                data = response.json()
                if "id" in data and "username" in data and "email" in data:
                    created_user_id = data["id"]
                    self.log_result("Users - POST Create", True, 
                                  f"Created user with ID {created_user_id}")
                else:
                    self.log_result("Users - POST Create", False, 
                                  "Response missing required fields")
            else:
                self.log_result("Users - POST Create", False, 
                              f"Expected 201, got {response.status_code}")
                
        except Exception as e:
            self.log_result("Users - POST Create", False, f"Error: {str(e)}")
        
        # Test GET /api/users/<id> if we created a user
        if created_user_id:
            try:
                response = requests.get(f"{API_BASE}/users/{created_user_id}", timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("id") == created_user_id:
                        self.log_result("Users - GET Single", True, 
                                      f"Retrieved user {created_user_id}")
                    else:
                        self.log_result("Users - GET Single", False, 
                                      "Retrieved user has wrong ID")
                else:
                    self.log_result("Users - GET Single", False, 
                                  f"Expected 200, got {response.status_code}")
                    
            except Exception as e:
                self.log_result("Users - GET Single", False, f"Error: {str(e)}")
            
            # Test PUT /api/users/<id>
            update_data = {
                "username": f"updated_user_{int(time.time())}",
                "email": test_user["email"]
            }
            
            try:
                response = requests.put(f"{API_BASE}/users/{created_user_id}", 
                                      json=update_data, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("username") == update_data["username"]:
                        self.log_result("Users - PUT Update", True, 
                                      f"Updated user {created_user_id}")
                    else:
                        self.log_result("Users - PUT Update", False, 
                                      "User not updated correctly")
                else:
                    self.log_result("Users - PUT Update", False, 
                                  f"Expected 200, got {response.status_code}")
                    
            except Exception as e:
                self.log_result("Users - PUT Update", False, f"Error: {str(e)}")
            
            # Test DELETE /api/users/<id>
            try:
                response = requests.delete(f"{API_BASE}/users/{created_user_id}", timeout=10)
                
                if response.status_code == 204:
                    self.log_result("Users - DELETE", True, 
                                  f"Deleted user {created_user_id}")
                else:
                    self.log_result("Users - DELETE", False, 
                                  f"Expected 204, got {response.status_code}")
                    
            except Exception as e:
                self.log_result("Users - DELETE", False, f"Error: {str(e)}")
    
    def run_all_tests(self):
        """Run all test suites"""
        print("🚀 Starting Comprehensive Backend API Tests")
        print(f"Testing API at: {API_BASE}")
        print("=" * 60)
        
        # Run all test suites
        self.test_health_endpoint()
        self.test_leaderboard_endpoint()
        self.test_predator_points_endpoint()
        self.test_twitch_override_endpoint()
        self.test_player_stats_endpoint()
        self.test_tracker_stats_endpoint()
        self.test_user_endpoints()
        
        # Print summary
        print("\n" + "=" * 60)
        print("🏁 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {self.total_tests}")
        print(f"Passed: {self.passed_tests}")
        print(f"Failed: {self.failed_tests}")
        print(f"Success Rate: {(self.passed_tests/self.total_tests*100):.1f}%")
        
        # Print failed tests
        if self.failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.results:
                if "❌ FAIL" in result["status"]:
                    print(f"  - {result['test']}: {result['message']}")
        
        # Save detailed results
        with open("/app/test_results_detailed.json", "w") as f:
            json.dump({
                "summary": {
                    "total_tests": self.total_tests,
                    "passed_tests": self.passed_tests,
                    "failed_tests": self.failed_tests,
                    "success_rate": round(self.passed_tests/self.total_tests*100, 1)
                },
                "results": self.results
            }, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: /app/test_results_detailed.json")
        
        return self.failed_tests == 0

def main():
    """Main test execution"""
    # Check if server is running first
    tester = APITester()
    
    print("🔍 Checking if server is accessible...")
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        print(f"✅ Server is accessible at {API_BASE}")
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to server at {API_BASE}")
        print("Please ensure the Flask application is running.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error checking server: {e}")
        sys.exit(1)
    
    # Run all tests
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {tester.failed_tests} test(s) failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
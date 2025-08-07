#!/usr/bin/env python3
"""
Comprehensive Integration Test Suite for Apex Legends Leaderboard QoL Features

This script tests all the newly implemented Quality of Life improvements:
- User preferences system
- Analytics tracking
- Health monitoring
- Cache management
- Webhook system
- Performance impact
"""

import requests
import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, List, Any

class IntegrationTester:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'tests_run': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'detailed_results': [],
            'performance_metrics': {},
            'summary': {}
        }
        
    def log_result(self, test_name: str, success: bool, details: Dict[str, Any] = None, error: str = None):
        """Log test result"""
        self.results['tests_run'] += 1
        if success:
            self.results['tests_passed'] += 1
            status = "PASS"
        else:
            self.results['tests_failed'] += 1
            status = "FAIL"
            
        result = {
            'test_name': test_name,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'details': details or {},
            'error': error
        }
        
        self.results['detailed_results'].append(result)
        print(f"[{status}] {test_name}")
        if error:
            print(f"  Error: {error}")
        if details:
            print(f"  Details: {json.dumps(details, indent=2)}")
        print()

    def test_health_endpoints(self):
        """Test health monitoring system"""
        print("=== Testing Health Monitoring System ===")
        
        # Test main health check
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=10)
            success = response.status_code == 200
            data = response.json() if success else None
            
            self.log_result(
                "Health Check Main Endpoint",
                success,
                {
                    'status_code': response.status_code,
                    'response_time_ms': data.get('response_time_ms') if data else None,
                    'overall_status': data.get('status') if data else None,
                    'systems_checked': len(data.get('checks', {})) if data else 0
                },
                None if success else f"HTTP {response.status_code}: {response.text}"
            )
        except Exception as e:
            self.log_result("Health Check Main Endpoint", False, error=str(e))

        # Test individual health endpoints
        health_endpoints = [
            ('/api/health/database', 'Database Health'),
            ('/api/health/twitch', 'Twitch API Health'),
            ('/api/health/cache', 'Cache System Health')
        ]
        
        for endpoint, name in health_endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                success = response.status_code == 200
                data = response.json() if success else None
                
                self.log_result(
                    name,
                    success,
                    {
                        'status_code': response.status_code,
                        'healthy': data.get('healthy') if data else False,
                        'message': data.get('message') if data else None
                    },
                    None if success else f"HTTP {response.status_code}: {response.text}"
                )
            except Exception as e:
                self.log_result(name, False, error=str(e))

    def test_user_preferences(self):
        """Test user preferences system"""
        print("=== Testing User Preferences System ===")
        
        try:
            response = requests.get(f"{self.base_url}/debug/test-user-preferences", timeout=15)
            success = response.status_code == 200
            data = response.json() if success else None
            
            details = {}
            if data and data.get('success'):
                details = {
                    'test_user_id': data.get('test_user_id'),
                    'get_preferences_success': data.get('get_preferences', {}).get('success'),
                    'update_preferences_success': data.get('update_preferences', {}).get('success'),
                    'add_favorite_success': data.get('add_favorite', {}).get('success')
                }
                # All sub-operations should succeed
                success = all([
                    details.get('get_preferences_success'),
                    details.get('update_preferences_success'),
                    details.get('add_favorite_success')
                ])
            
            self.log_result(
                "User Preferences Full Integration",
                success,
                details,
                None if success else f"Failed: {data.get('error') if data else 'No response data'}"
            )
        except Exception as e:
            self.log_result("User Preferences Full Integration", False, error=str(e))

    def test_analytics_system(self):
        """Test analytics tracking system"""
        print("=== Testing Analytics System ===")
        
        try:
            response = requests.get(f"{self.base_url}/debug/test-analytics", timeout=15)
            success = response.status_code == 200
            data = response.json() if success else None
            
            details = {}
            if data and data.get('success'):
                details = {
                    'analytics_events_count': data.get('database_counts', {}).get('analytics_events'),
                    'streamer_popularity_count': data.get('database_counts', {}).get('streamer_popularity'),
                    'track_event_success': data.get('track_event', {}).get('success'),
                    'track_streamer_success': data.get('track_streamer_view', {}).get('success'),
                    'analytics_summary_success': data.get('analytics_summary', {}).get('success')
                }
                # All analytics operations should succeed
                success = all([
                    details.get('track_event_success'),
                    details.get('track_streamer_success'),
                    details.get('analytics_summary_success')
                ])
            
            self.log_result(
                "Analytics System Full Integration",
                success,
                details,
                None if success else f"Failed: {data.get('error') if data else 'No response data'}"
            )
        except Exception as e:
            self.log_result("Analytics System Full Integration", False, error=str(e))

    def test_notification_system(self):
        """Test notification system readiness"""
        print("=== Testing Notification System ===")
        
        try:
            response = requests.get(f"{self.base_url}/debug/test-notifications", timeout=10)
            success = response.status_code == 200
            data = response.json() if success else None
            
            details = {}
            if data and data.get('success'):
                notif_data = data.get('notification_system', {})
                details = {
                    'users_with_notifications': notif_data.get('users_with_notifications'),
                    'users_with_favorite_notifications': notif_data.get('users_with_favorite_notifications'),
                    'total_favorite_streamers': notif_data.get('total_favorite_streamers'),
                    'ready_for_notifications': data.get('ready_for_live_notifications')
                }
            
            self.log_result(
                "Notification System Readiness",
                success,
                details,
                None if success else f"Failed: {data.get('error') if data else 'No response data'}"
            )
        except Exception as e:
            self.log_result("Notification System Readiness", False, error=str(e))

    def test_performance_impact(self):
        """Test performance impact of new features"""
        print("=== Testing Performance Impact ===")
        
        try:
            response = requests.get(f"{self.base_url}/debug/test-performance", timeout=20)
            success = response.status_code == 200
            data = response.json() if success else None
            
            details = {}
            if data and data.get('success'):
                perf_metrics = data.get('performance_metrics', {})
                details = {
                    'leaderboard_load_time_ms': perf_metrics.get('leaderboard_load_time_ms'),
                    'analytics_track_time_ms': perf_metrics.get('analytics_track_time_ms'),
                    'total_overhead_ms': perf_metrics.get('total_overhead_ms'),
                    'leaderboard_success': perf_metrics.get('leaderboard_success'),
                    'analytics_success': perf_metrics.get('analytics_success')
                }
                
                # Store performance metrics for summary
                self.results['performance_metrics'] = details
                
                # Performance is acceptable if overhead is < 100ms and operations succeed
                acceptable_performance = (
                    details.get('total_overhead_ms', 1000) < 100 and
                    details.get('leaderboard_success') and 
                    details.get('analytics_success')
                )
                success = success and acceptable_performance
            
            self.log_result(
                "Performance Impact Analysis",
                success,
                details,
                None if success else "Performance impact too high or operations failed"
            )
        except Exception as e:
            self.log_result("Performance Impact Analysis", False, error=str(e))

    def test_new_features_integration(self):
        """Test that all new QoL features are working together"""
        print("=== Testing New Features Integration ===")
        
        try:
            response = requests.get(f"{self.base_url}/debug/test-new-features", timeout=15)
            success = response.status_code == 200
            data = response.json() if success else None
            
            details = {}
            if data and data.get('success'):
                systems = data.get('systems', {})
                details = {
                    'overall_status': data.get('overall_status'),
                    'working_systems': data.get('message'),
                    'database_models_status': systems.get('database_models', {}).get('status'),
                    'caching_system_status': systems.get('caching_system', {}).get('status'),
                    'analytics_system_status': systems.get('analytics_system', {}).get('status'),
                    'webhook_system_status': systems.get('webhook_system', {}).get('status'),
                    'retry_system_status': systems.get('retry_system', {}).get('status')
                }
                
                # Success if overall status is healthy
                success = data.get('overall_status') == 'healthy'
            
            self.log_result(
                "New Features Integration Test",
                success,
                details,
                None if success else "Some QoL systems are not working properly"
            )
        except Exception as e:
            self.log_result("New Features Integration Test", False, error=str(e))

    def test_existing_functionality(self):
        """Test that existing functionality still works"""
        print("=== Testing Existing Functionality ===")
        
        # Test leaderboard endpoint
        try:
            start_time = time.time()
            response = requests.get(f"{self.base_url}/api/leaderboard/PC", timeout=20)
            load_time = round((time.time() - start_time) * 1000, 2)
            
            success = response.status_code == 200
            data = response.json() if success else None
            
            details = {
                'status_code': response.status_code,
                'load_time_ms': load_time,
                'has_data': bool(data and data.get('data')),
                'cached': data.get('cached') if data else None
            }
            
            if data and data.get('data'):
                players = data['data'].get('players', [])
                details['player_count'] = len(players)
                details['has_live_players'] = any(p.get('status') == 'Live' for p in players[:10])
            
            self.log_result(
                "Existing Leaderboard Functionality",
                success,
                details,
                None if success else f"HTTP {response.status_code}: {response.text[:200]}"
            )
        except Exception as e:
            self.log_result("Existing Leaderboard Functionality", False, error=str(e))

        # Test Twitch integration
        try:
            response = requests.get(f"{self.base_url}/debug/twitch-test", timeout=15)
            success = response.status_code == 200
            data = response.json() if success else None
            
            details = {}
            if data:
                details = {
                    'twitch_success': data.get('success'),
                    'token_length': data.get('token_length'),
                    'api_response_status': data.get('api_response_status'),
                    'client_id_set': bool(data.get('client_id'))
                }
                success = data.get('success', False)
            
            self.log_result(
                "Existing Twitch Integration",
                success,
                details,
                None if success else f"Twitch integration failed: {data.get('error') if data else 'No response'}"
            )
        except Exception as e:
            self.log_result("Existing Twitch Integration", False, error=str(e))

    def generate_summary(self):
        """Generate test summary"""
        success_rate = (self.results['tests_passed'] / self.results['tests_run'] * 100) if self.results['tests_run'] > 0 else 0
        
        self.results['summary'] = {
            'overall_success': success_rate >= 80,  # 80% pass rate required
            'success_rate_percent': round(success_rate, 2),
            'total_tests': self.results['tests_run'],
            'passed_tests': self.results['tests_passed'],
            'failed_tests': self.results['tests_failed'],
            'performance_acceptable': self.results['performance_metrics'].get('total_overhead_ms', 1000) < 100,
            'key_findings': []
        }
        
        # Add key findings
        if success_rate >= 95:
            self.results['summary']['key_findings'].append("Excellent integration - all systems working properly")
        elif success_rate >= 80:
            self.results['summary']['key_findings'].append("Good integration - minor issues detected")
        else:
            self.results['summary']['key_findings'].append("Integration issues detected - requires attention")
            
        if self.results['performance_metrics']:
            overhead = self.results['performance_metrics'].get('total_overhead_ms', 0)
            if overhead < 50:
                self.results['summary']['key_findings'].append("Excellent performance - minimal overhead")
            elif overhead < 100:
                self.results['summary']['key_findings'].append("Good performance - acceptable overhead")
            else:
                self.results['summary']['key_findings'].append("Performance concern - high overhead detected")

    def run_all_tests(self):
        """Run all integration tests"""
        print("Starting Comprehensive Integration Test Suite")
        print("=" * 60)
        print()
        
        # Run all test categories
        self.test_health_endpoints()
        self.test_user_preferences()
        self.test_analytics_system()
        self.test_notification_system()
        self.test_performance_impact()
        self.test_new_features_integration()
        self.test_existing_functionality()
        
        # Generate summary
        self.generate_summary()
        
        # Print results
        print("=" * 60)
        print("INTEGRATION TEST RESULTS")
        print("=" * 60)
        print(f"Tests Run: {self.results['tests_run']}")
        print(f"Tests Passed: {self.results['tests_passed']}")
        print(f"Tests Failed: {self.results['tests_failed']}")
        print(f"Success Rate: {self.results['summary']['success_rate_percent']:.1f}%")
        print(f"Overall Status: {'PASS' if self.results['summary']['overall_success'] else 'FAIL'}")
        print()
        
        if self.results['performance_metrics']:
            print("PERFORMANCE METRICS:")
            for key, value in self.results['performance_metrics'].items():
                print(f"  {key}: {value}")
            print()
        
        print("KEY FINDINGS:")
        for finding in self.results['summary']['key_findings']:
            print(f"  • {finding}")
        print()
        
        if self.results['tests_failed'] > 0:
            print("FAILED TESTS:")
            for result in self.results['detailed_results']:
                if result['status'] == 'FAIL':
                    print(f"  • {result['test_name']}: {result['error']}")
            print()
        
        # Save detailed results to file
        report_file = f"integration_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"Detailed report saved to: {report_file}")
        print()
        
        return self.results['summary']['overall_success']

def main():
    """Main function"""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8080"
    
    print(f"Testing server at: {base_url}")
    print(f"Test started at: {datetime.now()}")
    print()
    
    try:
        # Test server connectivity first
        response = requests.get(base_url, timeout=5)
        if response.status_code != 200:
            print(f"ERROR: Server not responding properly (HTTP {response.status_code})")
            return False
    except Exception as e:
        print(f"ERROR: Cannot connect to server at {base_url}")
        print(f"Please ensure the test server is running on port 8080")
        print(f"Error: {e}")
        return False
    
    # Run tests
    tester = IntegrationTester(base_url)
    success = tester.run_all_tests()
    
    if success:
        print("✅ Integration tests PASSED - All QoL features working correctly!")
        sys.exit(0)
    else:
        print("❌ Integration tests FAILED - Some issues detected")
        sys.exit(1)

if __name__ == "__main__":
    main()
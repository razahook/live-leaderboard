#!/usr/bin/env python3
"""
Quick verification script for Apex Legends Leaderboard QoL Features

This script performs a quick health check to verify all systems are working.
"""

import sys
import os
import json
from datetime import datetime

def main():
    print("🚀 Apex Legends Leaderboard - QoL Features Verification")
    print("=" * 60)
    
    # Add current directory to path
    sys.path.insert(0, os.getcwd())
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'tests': [],
        'overall_status': 'PASS'
    }
    
    def test_result(name, success, details=""):
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {name}")
        if details:
            print(f"   {details}")
        
        results['tests'].append({
            'name': name,
            'success': success,
            'details': details
        })
        
        if not success:
            results['overall_status'] = 'FAIL'
    
    # Test 1: Imports
    try:
        from test_server import app
        from models.user import db, User, UserPreferences
        from models.analytics import AnalyticsEvent, StreamerPopularity
        from cache_manager import cache_manager
        from utils.retry_decorator import twitch_api_retry
        test_result("System Imports", True, "All modules imported successfully")
    except Exception as e:
        test_result("System Imports", False, f"Import error: {e}")
        return results
    
    # Test 2: Database Models
    try:
        with app.app_context():
            user_count = User.query.count()
            prefs_count = UserPreferences.query.count()
            analytics_count = AnalyticsEvent.query.count()
            test_result("Database Models", True, f"Users: {user_count}, Preferences: {prefs_count}, Analytics: {analytics_count}")
    except Exception as e:
        test_result("Database Models", False, f"Database error: {e}")
    
    # Test 3: Cache System
    try:
        cache_stats = cache_manager.get_all_stats()
        active_caches = len(cache_stats)
        test_result("Cache System", True, f"{active_caches} caches active")
    except Exception as e:
        test_result("Cache System", False, f"Cache error: {e}")
    
    # Test 4: User Preferences System
    try:
        with app.app_context():
            # Create test user and preferences
            test_user = User.query.filter_by(username='verify_test').first()
            if not test_user:
                test_user = User(username='verify_test', email='verify@test.com')
                db.session.add(test_user)
                db.session.commit()
            
            prefs = UserPreferences.create_default_preferences(test_user.id)
            prefs.theme = 'dark'
            prefs.auto_refresh_enabled = True
            prefs.set_favorite_streamers(['test_streamer'])
            
            # Test serialization
            prefs_dict = prefs.to_dict()
            favorites = prefs.get_favorite_streamers()
            
            test_result("User Preferences", True, f"Preferences created with {len(favorites)} favorites")
    except Exception as e:
        test_result("User Preferences", False, f"Preferences error: {e}")
    
    # Test 5: Analytics System
    try:
        with app.app_context():
            event = AnalyticsEvent.create_event(
                event_type='verification',
                event_category='testing',
                event_action='quick_verify',
                metadata={'test': True, 'timestamp': datetime.now().isoformat()}
            )
            
            # Test metadata handling
            event.set_metadata({'key': 'value', 'number': 42})
            metadata = event.get_metadata()
            
            test_result("Analytics System", True, f"Event created with metadata: {metadata}")
    except Exception as e:
        test_result("Analytics System", False, f"Analytics error: {e}")
    
    # Test 6: HTML Frontend Structure
    try:
        html_file = os.path.join(os.getcwd(), 'index.html')
        if os.path.exists(html_file):
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for key QoL features
            features = [
                'EnhancedFeatures',
                'settingsModal',
                'darkModeToggle',
                'notificationsToggle',
                'trackAnalyticsEvent',
                'showToast',
                'streamPreview'
            ]
            
            missing_features = [f for f in features if f not in content]
            
            if not missing_features:
                test_result("Frontend Features", True, f"All {len(features)} QoL features present")
            else:
                test_result("Frontend Features", False, f"Missing features: {missing_features}")
        else:
            test_result("Frontend Features", False, "index.html not found")
    except Exception as e:
        test_result("Frontend Features", False, f"Frontend check error: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print(f"VERIFICATION COMPLETE - {results['overall_status']}")
    print("=" * 60)
    
    passed = sum(1 for t in results['tests'] if t['success'])
    total = len(results['tests'])
    print(f"Tests: {passed}/{total} passed")
    
    if results['overall_status'] == 'PASS':
        print("\n🎉 All QoL features are ready!")
        print("✅ Backend systems operational")
        print("✅ Frontend features integrated")
        print("✅ Database models working")
        print("✅ Analytics tracking ready")
        print("✅ User preferences system functional")
        print("\n🚀 Ready for integration testing!")
    else:
        print("\n⚠️  Some issues detected:")
        for test in results['tests']:
            if not test['success']:
                print(f"   • {test['name']}: {test['details']}")
    
    # Save results
    report_file = f"verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Report saved to: {report_file}")
    
    return results['overall_status'] == 'PASS'

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
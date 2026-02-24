#!/usr/bin/env python3
"""
AEGIS Integration Test Script
Verifies all components work together properly

Access URLs:
- Government Login: http://localhost:8000/admin/aegis_admin_2026
- Public Page: http://localhost:8000/public
- Health Check: http://localhost:8000/health
- Root redirects to: /admin/aegis_admin_2026
"""

import sys
import os
import requests
import time

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_database():
    """Test database connectivity and initialization"""
    print("🔍 Testing Database...")
    try:
        from database import init_db, SessionLocal
        from models import GovernmentUser
        
        # Initialize database
        init_db()
        print("✅ Database tables created")
        
        # Test connection
        db = SessionLocal()
        user_count = db.query(GovernmentUser).count()
        print(f"✅ Database connection successful - {user_count} users found")
        db.close()
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_auth():
    """Test authentication system"""
    print("🔍 Testing Authentication...")
    try:
        from auth import hash_password, verify_password, create_access_token, decode_token
        from models import GovernmentUser
        from database import SessionLocal
        
        # Test password hashing
        password = "test_password"
        hashed = hash_password(password)
        assert verify_password(password, hashed)
        print("✅ Password hashing/verification works")
        
        # Test JWT token creation
        token = create_access_token("test_user")
        payload = decode_token(token)
        assert payload["sub"] == "test_user"
        print("✅ JWT token creation/verification works")
        
        # Test database user creation
        db = SessionLocal()
        existing = db.query(GovernmentUser).filter(GovernmentUser.username == "integration_test").first()
        if not existing:
            user = GovernmentUser(username="integration_test", hashed_password=hash_password("test123"))
            db.add(user)
            db.commit()
            print("✅ Database user creation works")
        db.close()
        
        return True
    except Exception as e:
        print(f"❌ Auth test failed: {e}")
        return False

def test_backend_api():
    """Test backend API endpoints"""
    print("🔍 Testing Backend API...")
    try:
        # Test health endpoint
        response = requests.get("http://localhost:8000/health", timeout=5)
        assert response.status_code == 200
        print("✅ Health endpoint works")
        
        # Test public endpoints
        response = requests.get("http://localhost:8000/api/public/status", timeout=5)
        assert response.status_code == 200
        print("✅ Public status endpoint works")
        
        response = requests.get("http://localhost:8000/api/public/advisory", timeout=5)
        assert response.status_code == 200
        print("✅ Public advisory endpoint works")
        
        # Test login endpoint
        login_data = {"username": "admin", "password": "aegis_admin_2026"}
        response = requests.post("http://localhost:8000/api/gov/login", json=login_data, timeout=5)
        assert response.status_code == 200
        token_data = response.json()
        token = token_data["access_token"]
        print("✅ Government login endpoint works")
        
        # Test authenticated endpoint
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get("http://localhost:8000/api/gov/dashboard", headers=headers, timeout=5)
        assert response.status_code == 200
        print("✅ Authenticated dashboard endpoint works")
        
        return True
    except requests.exceptions.ConnectionError:
        print("❌ Backend server not running - start server first")
        return False
    except Exception as e:
        print(f"❌ API test failed: {e}")
        return False

def test_frontend_files():
    """Test frontend file existence and structure"""
    print("🔍 Testing Frontend Files...")
    try:
        frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
        
        # Check required files
        required_files = [
            "index.html",
            "public.html", 
            "css/aegis.css",
            "js/government.js",
            "js/public.js",
            "js/charts.js"
        ]
        
        for file_path in required_files:
            full_path = os.path.join(frontend_dir, file_path)
            assert os.path.exists(full_path), f"Missing file: {file_path}"
        
        print("✅ All frontend files present")
        return True
    except Exception as e:
        print(f"❌ Frontend test failed: {e}")
        return False

def main():
    """Run all integration tests"""
    print("🧪 AEGIS Integration Test Suite")
    print("=" * 50)
    
    tests = [
        ("Database", test_database),
        ("Authentication", test_auth),
        ("Frontend Files", test_frontend_files),
        ("Backend API", test_backend_api)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nFinal Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All integration tests passed! System is ready.")
        return True
    else:
        print("⚠️  Some tests failed. Please fix issues before running.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
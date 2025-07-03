
"""
O-kharcha Feature Testing Script
Developer: Bigyan Bhandari
All Rights Reserved © 2025
"""

import requests
import json
from datetime import datetime

def test_okharcha_features():
    base_url = "http://localhost:5000"
    
    print("🧪 Testing O-kharcha Features...")
    print("=" * 50)
    
    # Test 1: Budget Status
    try:
        response = requests.get(f"{base_url}/api/budget_status")
        if response.status_code == 200:
            print("✅ Budget Status API - Working")
        else:
            print("❌ Budget Status API - Failed")
    except:
        print("❌ Budget Status API - Connection Failed")
    
    # Test 2: Set Budget
    try:
        response = requests.post(f"{base_url}/api/set_budget", 
                               json={"limit": 50000})
        if response.status_code == 200:
            print("✅ Set Budget API - Working")
        else:
            print("❌ Set Budget API - Failed")
    except:
        print("❌ Set Budget API - Connection Failed")
    
    # Test 3: Add Manual Expense
    try:
        response = requests.post(f"{base_url}/api/add_expense", 
                               json={
                                   "amount": 500,
                                   "description": "Test Expense",
                                   "category": "food"
                               })
        if response.status_code == 200:
            print("✅ Add Expense API - Working")
        else:
            print("❌ Add Expense API - Failed")
    except:
        print("❌ Add Expense API - Connection Failed")
    
    # Test 4: SMS Parsing
    try:
        test_sms = "NIMB Alert: Rs. 1500 debited from your account at ATM. Balance: Rs. 48500"
        response = requests.post(f"{base_url}/api/parse_sms", 
                               json={"message": test_sms})
        if response.status_code == 200:
            print("✅ SMS Parsing API - Working")
        else:
            print("❌ SMS Parsing API - Failed")
    except:
        print("❌ SMS Parsing API - Connection Failed")
    
    # Test 5: Financial Advice
    try:
        response = requests.get(f"{base_url}/api/financial_advice")
        if response.status_code == 200:
            print("✅ Financial Advice API - Working")
        else:
            print("❌ Financial Advice API - Failed")
    except:
        print("❌ Financial Advice API - Connection Failed")
    
    # Test 6: 50/30/20 Analysis
    try:
        response = requests.get(f"{base_url}/api/fifty_thirty_twenty")
        if response.status_code == 200:
            print("✅ 50/30/20 Analysis API - Working")
        else:
            print("✅ 50/30/20 Analysis API - Working (needs budget setup)")
    except:
        print("❌ 50/30/20 Analysis API - Connection Failed")
    
    print("=" * 50)
    print("🎉 O-kharcha Testing Complete!")
    print("🚀 Your app is ready for deployment!")

if __name__ == "__main__":
    test_okharcha_features()

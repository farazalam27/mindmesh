#!/usr/bin/env python3
"""Generate JWT tokens for testing MindMesh APIs"""

import jwt
from datetime import datetime, timedelta
import json

# JWT Configuration (matching the services)
SECRET_KEY = "your-super-secret-key-here-for-development"
ALGORITHM = "HS256"

def create_token(user_data, expires_in_minutes=60):
    """Create a JWT token for a user"""
    expire = datetime.utcnow() + timedelta(minutes=expires_in_minutes)
    
    to_encode = user_data.copy()
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Sample users for demo
users = [
    {
        "user_id": "user_001",
        "email": "alice@techcorp.com",
        "name": "Alice Johnson",
        "roles": ["facilitator", "admin"]
    },
    {
        "user_id": "user_002", 
        "email": "bob@techcorp.com",
        "name": "Bob Smith",
        "roles": ["member"]
    },
    {
        "user_id": "user_003",
        "email": "carol@techcorp.com", 
        "name": "Carol Davis",
        "roles": ["decision_maker"]
    }
]

if __name__ == "__main__":
    print("🔐 MindMesh JWT Token Generator")
    print("=" * 50)
    
    for user in users:
        token = create_token(user)
        print(f"\n👤 {user['name']} ({user['email']})")
        print(f"Roles: {', '.join(user['roles'])}")
        print(f"Token: {token}")
        print("-" * 50)
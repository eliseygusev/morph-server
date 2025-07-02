import httpx
import jwt
import asyncio
import datetime
import json

async def test_server():
    base_url = "http://localhost:8000"
    secret = "your-secret-key"
    
    payload = {
        "sub": "test-user",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        print("1. Testing health endpoint...")
        response = await client.get(f"{base_url}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}\n")
        
        print("2. Testing process endpoint (requires real GitHub token)...")
        test_data = {
            "access_token": "your-github-token",
            "repo_name": "your-username/test-repo",
            "branch_name": f"test-branch-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "prompt": "Create a simple hello world Python function",
            "callback_url": None
        }
        
        print("   Request data:")
        print(f"   - Repo: {test_data['repo_name']}")
        print(f"   - Branch: {test_data['branch_name']}")
        print(f"   - Prompt: {test_data['prompt']}")
        
        if test_data['access_token'] == "your-github-token":
            print("\n   ⚠️  Please update the test_data with a real GitHub token and repo to test")
        else:
            response = await client.post(
                f"{base_url}/process",
                headers=headers,
                json=test_data,
                timeout=120.0
            )
            print(f"\n   Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"   Branch: {result['branch_name']}")
                print(f"   Changed files: {len(result['changed_files']['added'])} added, "
                      f"{len(result['changed_files']['modified'])} modified, "
                      f"{len(result['changed_files']['deleted'])} deleted")
                if result['patch']:
                    print(f"   Patch preview:\n{result['patch'][:200]}...")
            else:
                print(f"   Error: {response.text}")

if __name__ == "__main__":
    print("Morph Server Test Script")
    print("========================\n")
    print("Make sure the server is running: python main.py\n")
    
    asyncio.run(test_server())
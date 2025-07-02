import os
import subprocess
import time
from typing import Optional

def run_with_morph(port: int = 8000, jwt_secret: Optional[str] = None):
    """
    Run the server and expose it via Morph Cloud SDK.
    
    This should be run within a Morph Cloud instance.
    """
    
    if jwt_secret:
        os.environ["JWT_SECRET_KEY"] = jwt_secret
    
    os.environ["PORT"] = str(port)
    
    server_process = subprocess.Popen(
        ["python", "main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    time.sleep(2)
    
    try:
        from morphcloud import get_current_instance
        
        instance = get_current_instance()
        service_url = instance.expose_http_service("morph-claude-server", port)
        
        print(f"Morph Claude Server is running!")
        print(f"Internal URL: http://0.0.0.0:{port}")
        print(f"Public URL: {service_url}")
        print(f"\nEndpoints:")
        print(f"  Health: {service_url}/health")
        print(f"  Process: {service_url}/process (requires JWT auth)")
        
        server_process.wait()
        
    except ImportError:
        print("Morph Cloud SDK not available. Running locally.")
        print(f"Server is running at http://0.0.0.0:{port}")
        print(f"\nEndpoints:")
        print(f"  Health: http://0.0.0.0:{port}/health")
        print(f"  Process: http://0.0.0.0:{port}/process (requires JWT auth)")
        
        server_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server_process.terminate()
        server_process.wait()


if __name__ == "__main__":
    jwt_secret = os.environ.get("JWT_SECRET_KEY", "your-secret-key-here")
    port = int(os.environ.get("PORT", 8000))
    
    run_with_morph(port, jwt_secret)
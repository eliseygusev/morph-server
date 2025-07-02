import os
import asyncio
import tempfile
import shutil
from typing import Optional, Dict, Any
from pathlib import Path

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.authentication import requires
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

import httpx
from claude_code_sdk import query, ClaudeCodeOptions, Message

from github_bot import GitHubAPIBot
from auth import get_auth_middleware


async def process_claude_request(request: Request) -> JSONResponse:
    try:
        data = await request.json()
        
        access_token = data.get("access_token")
        branch_name = data.get("branch_name")
        prompt = data.get("prompt")
        repo_name = data.get("repo_name")
        callback_url = data.get("callback_url")
        
        if not all([access_token, branch_name, prompt, repo_name]):
            return JSONResponse(
                {"error": "Missing required fields: access_token, branch_name, prompt, repo_name"},
                status_code=400
            )
        
        bot = GitHubAPIBot(access_token)
        
        try:
            bot.create_branch(repo_name, branch_name)
        except Exception as e:
            if "Reference already exists" not in str(e):
                return JSONResponse({"error": f"Failed to create branch: {str(e)}"}, status_code=400)
        
        files = bot.get_all_files(repo_name, branch_name)
        bot.initialize_tracking(repo_name, branch_name)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            for file_path, content in files.items():
                file_full_path = temp_path / file_path
                file_full_path.parent.mkdir(parents=True, exist_ok=True)
                
                if content != "[Binary file]":
                    file_full_path.write_text(content)
            
            os.chdir(temp_dir)
            
            messages = []
            async for message in query(
                prompt=prompt,
                options=ClaudeCodeOptions(
                    max_turns=3,
                    permission_mode=''
                )
            ):
                messages.append(message)
            
            for root, dirs, filenames in os.walk(temp_dir):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(file_path, temp_dir)
                    
                    if relative_path.startswith('.'):
                        continue
                    
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                        
                        if relative_path in bot.initial_files:
                            if content != bot.initial_files[relative_path]:
                                bot.track_file_change(relative_path, content)
                        else:
                            bot.track_file_change(relative_path, content)
                    except:
                        pass
            
            for file_path in list(bot.initial_files.keys()):
                full_path = temp_path / file_path
                if not full_path.exists():
                    bot.track_file_deletion(file_path)
        
        patch = bot.generate_patch()
        changed_files = bot.get_changed_files_summary()
        
        result = {
            "status": "success",
            "branch_name": branch_name,
            "patch": patch,
            "changed_files": changed_files,
            "claude_messages": [{"type": msg.type, "content": msg.content} for msg in messages]
        }
        
        if callback_url:
            asyncio.create_task(send_callback(callback_url, result))
        
        return JSONResponse(result)
    
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def send_callback(callback_url: str, data: Dict[str, Any]) -> None:
    try:
        async with httpx.AsyncClient() as client:
            await client.post(callback_url, json=data, timeout=30.0)
    except Exception as e:
        print(f"Failed to send callback to {callback_url}: {e}")


@requires('authenticated')
async def claude_endpoint(request: Request) -> JSONResponse:
    return await process_claude_request(request)


async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "healthy", "service": "morph-server"})


def create_app(jwt_secret: Optional[str] = None) -> Starlette:
    middleware = [
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
    ]
    
    app = Starlette(
        routes=[
            Route("/health", health_check, methods=["GET"]),
            Route("/process", claude_endpoint, methods=["POST"]),
        ],
        middleware=middleware
    )
    
    app = get_auth_middleware(app, jwt_secret)
    
    return app


if __name__ == "__main__":
    import uvicorn
    
    jwt_secret = os.environ.get("JWT_SECRET_KEY")
    port = int(os.environ.get("PORT", 8000))
    
    app = create_app(jwt_secret)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=False
    )

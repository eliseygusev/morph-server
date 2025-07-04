# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "starlette>=0.37.2",
#     "uvicorn[standard]>=0.30.1",
#     "PyGithub>=2.3.0",
#     "claude-code-sdk>=0.0.14",
#     "httpx>=0.27.0",
#     "python-multipart>=0.0.9"
# ]
# ///

import os
import asyncio
import tempfile
import shutil
from typing import Optional, Dict, Any, Set, Tuple
from pathlib import Path
import httpx
import base64
import difflib

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from claude_code_sdk import query, ClaudeCodeOptions, Message
from github import Github


class GitHubAPIBot:
    def __init__(self, access_token: str):
        self.g = Github(access_token)
        self.initial_files: Dict[str, str] = {}
        self.current_files: Dict[str, str] = {}
        
    def get_default_branch_sha(self, repo_name: str) -> str:
        repo = self.g.get_repo(repo_name)
        default_branch = repo.default_branch
        ref = repo.get_git_ref(f"heads/{default_branch}")
        return ref.object.sha
    
    def create_branch(self, repo_name: str, branch_name: str, from_sha: Optional[str] = None) -> None:
        repo = self.g.get_repo(repo_name)
        
        if not from_sha:
            from_sha = self.get_default_branch_sha(repo_name)
        
        ref = repo.create_git_ref(
            ref=f"refs/heads/{branch_name}",
            sha=from_sha
        )
        return ref
    
    def get_file_content(self, repo_name: str, file_path: str, branch: Optional[str] = None) -> str:
        repo = self.g.get_repo(repo_name)
        file_content = repo.get_contents(file_path, ref=branch)
        return file_content.decoded_content.decode()
    
    def update_file(self, repo_name: str, file_path: str, content: str, commit_message: str, branch: str) -> None:
        repo = self.g.get_repo(repo_name)
        
        try:
            contents = repo.get_contents(file_path, ref=branch)
            repo.update_file(
                path=file_path,
                message=commit_message,
                content=content,
                sha=contents.sha,
                branch=branch
            )
        except:
            repo.create_file(
                path=file_path,
                message=commit_message,
                content=content,
                branch=branch
            )
    
    def get_all_files(self, repo_name: str, branch: Optional[str] = None) -> Dict[str, str]:
        repo = self.g.get_repo(repo_name)
        
        if not branch:
            branch = repo.default_branch
        
        contents = repo.get_contents("", ref=branch)
        
        files = {}
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                contents.extend(repo.get_contents(file_content.path, ref=branch))
            else:
                try:
                    files[file_content.path] = file_content.decoded_content.decode()
                except:
                    files[file_content.path] = "[Binary file]"
        
        return files
    
    def initialize_tracking(self, repo_name: str, branch: str) -> None:
        self.initial_files = self.get_all_files(repo_name, branch)
        self.current_files = self.initial_files.copy()
    
    def track_file_change(self, file_path: str, content: str) -> None:
        self.current_files[file_path] = content
    
    def track_file_deletion(self, file_path: str) -> None:
        if file_path in self.current_files:
            del self.current_files[file_path]
    
    def get_changes(self) -> Tuple[Set[str], Set[str], Set[str]]:
        initial_keys = set(self.initial_files.keys())
        current_keys = set(self.current_files.keys())
        
        added_files = current_keys - initial_keys
        deleted_files = initial_keys - current_keys
        
        modified_files = set()
        for file_path in initial_keys & current_keys:
            if self.initial_files[file_path] != self.current_files[file_path]:
                modified_files.add(file_path)
        
        return added_files, modified_files, deleted_files
    
    def generate_patch(self) -> str:
        added, modified, deleted = self.get_changes()
        patch_lines = []
        
        for file_path in sorted(deleted):
            patch_lines.append(f"--- a/{file_path}")
            patch_lines.append(f"+++ /dev/null")
            lines = self.initial_files[file_path].splitlines(keepends=True)
            for i, line in enumerate(lines, 1):
                patch_lines.append(f"-{line.rstrip()}")
            patch_lines.append("")
        
        for file_path in sorted(modified):
            patch_lines.append(f"--- a/{file_path}")
            patch_lines.append(f"+++ b/{file_path}")
            
            original_lines = self.initial_files[file_path].splitlines(keepends=True)
            new_lines = self.current_files[file_path].splitlines(keepends=True)
            
            diff = list(difflib.unified_diff(
                original_lines,
                new_lines,
                lineterm=''
            ))
            
            if len(diff) > 2:
                patch_lines.extend(diff[2:])
            patch_lines.append("")
        
        for file_path in sorted(added):
            patch_lines.append(f"--- /dev/null")
            patch_lines.append(f"+++ b/{file_path}")
            lines = self.current_files[file_path].splitlines(keepends=True)
            for line in lines:
                patch_lines.append(f"+{line.rstrip()}")
            patch_lines.append("")
        
        return "\n".join(patch_lines)
    
    def get_changed_files_summary(self) -> Dict[str, Dict[str, str]]:
        added, modified, deleted = self.get_changes()
        
        summary = {
            "added": {},
            "modified": {},
            "deleted": {}
        }
        
        for file_path in added:
            summary["added"][file_path] = self.current_files[file_path]
        
        for file_path in modified:
            summary["modified"][file_path] = self.current_files[file_path]
        
        for file_path in deleted:
            summary["deleted"][file_path] = self.initial_files[file_path]
        
        return summary


async def send_callback(callback_url: str, data: Dict[str, Any]) -> None:
    """Send a callback to the specified URL with the result data."""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(callback_url, json=data, timeout=30.0)
    except Exception as e:
        print(f"Failed to send callback to {callback_url}: {str(e)}")


async def process_claude_request(request: Request) -> JSONResponse:
    try:
        data = await request.json()
        
        access_token = data.get("access_token")
        branch_name = data.get("branch_name")
        prompt = data.get("prompt")
        repo_name = data.get("repo_name")
        callback_url = data.get("callback_url")
        
        if not all([access_token, branch_name, prompt, repo_name, callback_url]):
            return JSONResponse(
                {"error": "Missing required fields: access_token, branch_name, prompt, repo_name, callback_url"},
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
            
            messages: list[Message] = []
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
            "claude_messages": [str(msg) for msg in messages]
        }
        
        # Send callback to the provided URL
        await send_callback(callback_url, result)
        
        return JSONResponse(result)
    
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def claude_endpoint(request: Request) -> JSONResponse:
    return await process_claude_request(request)


async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "healthy", "service": "morph-server"})


def create_app() -> Starlette:
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
    
    return app


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8000))
    
    app = create_app()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=False
    )
from github import Github
import base64
from typing import Dict, Optional, Set, Tuple
import difflib

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
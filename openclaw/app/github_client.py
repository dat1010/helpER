import base64
import logging
from typing import Dict, Optional, Tuple

import requests


class GitHubClient:
    def __init__(self, token: str) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        self.log = logging.getLogger("openclaw.github")

    def _request(self, method: str, path: str, **kwargs) -> Dict:
        url = f"https://api.github.com{path}"
        resp = self.session.request(method, url, timeout=30, **kwargs)
        if resp.status_code >= 400:
            self.log.error("GitHub API error %s %s: %s", method, path, resp.text)
            resp.raise_for_status()
        if not resp.text.strip():
            return {}
        return resp.json()

    @staticmethod
    def _split_repo(repo: str) -> Tuple[str, str]:
        owner, name = repo.split("/", 1)
        return owner, name

    def get_repo_info(self, repo: str) -> Dict:
        owner, name = self._split_repo(repo)
        return self._request("GET", f"/repos/{owner}/{name}")

    def get_ref_sha(self, repo: str, ref: str) -> str:
        owner, name = self._split_repo(repo)
        resp = self._request("GET", f"/repos/{owner}/{name}/git/ref/heads/{ref}")
        return str(resp["object"]["sha"])

    def ensure_branch(self, repo: str, branch: str, from_sha: str) -> None:
        owner, name = self._split_repo(repo)
        try:
            self._request(
                "POST",
                f"/repos/{owner}/{name}/git/refs",
                json={"ref": f"refs/heads/{branch}", "sha": from_sha},
            )
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 422:
                self.log.info("Branch %s already exists in %s", branch, repo)
            else:
                raise

    def get_content_sha(self, repo: str, path: str, branch: str) -> Optional[str]:
        owner, name = self._split_repo(repo)
        resp = self.session.get(
            f"https://api.github.com/repos/{owner}/{name}/contents/{path}",
            params={"ref": branch},
            timeout=30,
        )
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            self.log.error("GitHub content lookup failed: %s", resp.text)
            resp.raise_for_status()
        data = resp.json()
        return data.get("sha")

    def put_text_file(
        self, repo: str, branch: str, path: str, content: str, message: str
    ) -> None:
        owner, name = self._split_repo(repo)
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        existing_sha = self.get_content_sha(repo, path, branch)
        payload = {"message": message, "content": encoded, "branch": branch}
        if existing_sha:
            payload["sha"] = existing_sha
        self._request("PUT", f"/repos/{owner}/{name}/contents/{path}", json=payload)

    def find_open_pr(self, repo: str, head_branch: str) -> Optional[Dict]:
        owner, name = self._split_repo(repo)
        prs = self._request(
            "GET",
            f"/repos/{owner}/{name}/pulls",
            params={"state": "open", "head": f"{owner}:{head_branch}", "per_page": 1},
        )
        if isinstance(prs, list) and prs:
            return prs[0]
        return None

    def create_pr(
        self, repo: str, title: str, body: str, head: str, base: str
    ) -> Dict:
        owner, name = self._split_repo(repo)
        return self._request(
            "POST",
            f"/repos/{owner}/{name}/pulls",
            json={"title": title, "body": body, "head": head, "base": base, "draft": False},
        )

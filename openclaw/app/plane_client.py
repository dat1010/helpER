import logging
from typing import Dict, List, Optional

import requests


class PlaneClient:
    def __init__(self, base_url: str, api_token: str, workspace_slug: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.workspace_slug = workspace_slug
        self.session = requests.Session()
        self.session.headers.update(
            {
                "x-api-key": api_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        self.log = logging.getLogger("openclaw.plane")

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(self, method: str, path: str, **kwargs) -> Dict:
        resp = self.session.request(method, self._url(path), timeout=30, **kwargs)
        if resp.status_code >= 400:
            self.log.error("Plane API error %s %s: %s", method, path, resp.text)
            resp.raise_for_status()
        if not resp.text.strip():
            return {}
        return resp.json()

    def list_work_items(self, project_id: str) -> List[Dict]:
        path = (
            f"/api/v1/workspaces/{self.workspace_slug}/projects/"
            f"{project_id}/work-items/"
        )
        payload = self._request(
            "GET",
            path,
            params={"limit": 100, "expand": "state,labels,assignees"},
        )
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("results") or payload.get("data") or []
        return []

    def list_states(self, project_id: str) -> List[Dict]:
        path = (
            f"/api/v1/workspaces/{self.workspace_slug}/projects/"
            f"{project_id}/states/"
        )
        payload = self._request("GET", path, params={"limit": 100})
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("results") or payload.get("data") or []
        return []

    def find_state_id(self, project_id: str, state_name: str) -> Optional[str]:
        target = state_name.strip().lower()
        for state in self.list_states(project_id):
            name = str(state.get("name", "")).strip().lower()
            if name == target:
                return str(state.get("id"))
        return None

    def update_work_item_state(self, project_id: str, work_item_id: str, state_id: str) -> None:
        path = (
            f"/api/v1/workspaces/{self.workspace_slug}/projects/"
            f"{project_id}/work-items/{work_item_id}/"
        )
        self._request("PATCH", path, json={"state": state_id})

    def add_comment(self, project_id: str, work_item_id: str, comment_html: str) -> None:
        path = (
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/"
            f"work-items/{work_item_id}/comments/"
        )
        self._request("POST", path, json={"comment_html": comment_html})

    @staticmethod
    def item_state_name(item: Dict) -> str:
        state = item.get("state") or item.get("state_detail") or item.get("state_details")
        if isinstance(state, dict):
            return str(state.get("name", "")).strip()
        return str(item.get("state_name", "")).strip()

    @staticmethod
    def item_label_names(item: Dict) -> List[str]:
        labels = item.get("labels") or item.get("label_details") or []
        names = []
        for label in labels:
            if isinstance(label, dict):
                names.append(str(label.get("name", "")).strip())
            else:
                names.append(str(label).strip())
        return [n for n in names if n]

import json
import os
from dataclasses import dataclass
from typing import Dict, List


def _split_csv(value: str) -> List[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass
class Config:
    poll_seconds: int
    log_level: str

    plane_base_url: str
    plane_api_token: str
    plane_workspace_slug: str
    plane_project_ids: List[str]
    plane_state_planning: str
    plane_state_planned: str
    plane_state_implement: str
    plane_state_review: str
    plane_label_needs_plan: str
    plane_label_ready_for_impl: str

    github_token: str
    github_default_repo: str
    project_repo_map: Dict[str, str]

    automation_file_prefix: str


    @staticmethod
    def from_env() -> "Config":
        project_repo_map_raw = os.getenv("PROJECT_REPO_MAP", "{}")
        try:
            project_repo_map = json.loads(project_repo_map_raw)
            if not isinstance(project_repo_map, dict):
                project_repo_map = {}
        except json.JSONDecodeError:
            project_repo_map = {}

        return Config(
            poll_seconds=int(os.getenv("OPENCLAW_POLL_SECONDS", "60")),
            log_level=os.getenv("OPENCLAW_LOG_LEVEL", "INFO"),
            plane_base_url=os.getenv("PLANE_BASE_URL", "").rstrip("/"),
            plane_api_token=os.getenv("PLANE_API_TOKEN", ""),
            plane_workspace_slug=os.getenv("PLANE_WORKSPACE_SLUG", ""),
            plane_project_ids=_split_csv(os.getenv("PLANE_PROJECT_IDS", "")),
            plane_state_planning=os.getenv("PLANE_STATE_PLANNING", "Planning"),
            plane_state_planned=os.getenv("PLANE_STATE_PLANNED", "Planned"),
            plane_state_implement=os.getenv("PLANE_STATE_IMPLEMENT", "Implement"),
            plane_state_review=os.getenv("PLANE_STATE_REVIEW", "Review"),
            plane_label_needs_plan=os.getenv("PLANE_LABEL_NEEDS_PLAN", "needs-plan"),
            plane_label_ready_for_impl=os.getenv(
                "PLANE_LABEL_READY_FOR_IMPL", "ready-for-openclaw"
            ),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            github_default_repo=os.getenv("GITHUB_DEFAULT_REPO", ""),
            project_repo_map={str(k): str(v) for k, v in project_repo_map.items()},
            automation_file_prefix=os.getenv(
                "OPENCLAW_AUTOMATION_FILE_PREFIX", ".openclaw/tickets"
            ),
        )

    def repo_for_project(self, project_id: str) -> str:
        return self.project_repo_map.get(project_id, self.github_default_repo)

    def validate(self) -> List[str]:
        errors = []
        if not self.plane_base_url:
            errors.append("PLANE_BASE_URL is required")
        if not self.plane_api_token:
            errors.append("PLANE_API_TOKEN is required")
        if not self.plane_workspace_slug:
            errors.append("PLANE_WORKSPACE_SLUG is required")
        if not self.plane_project_ids:
            errors.append("PLANE_PROJECT_IDS must contain at least one project ID")
        if not self.github_token:
            errors.append("GITHUB_TOKEN is required")
        if not self.github_default_repo and not self.project_repo_map:
            errors.append(
                "Set GITHUB_DEFAULT_REPO or PROJECT_REPO_MAP for implementation mode"
            )
        return errors

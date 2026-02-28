import logging
import re
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from .config import Config
from .github_client import GitHubClient
from .metrics import Metrics
from .plane_client import PlaneClient


class Engine:
    def __init__(self, cfg: Config, plane: PlaneClient, github: GitHubClient, metrics: Metrics):
        self.cfg = cfg
        self.plane = plane
        self.github = github
        self.metrics = metrics

        self.log = logging.getLogger("openclaw.engine")
        self.stop_event = threading.Event()

        self.active_impl_ticket: Optional[Tuple[str, str]] = None
        self.active_impl_started: Optional[str] = None
        self.impl_lock = threading.Lock()

        self.planned_tickets: Set[Tuple[str, str]] = set()
        self.reviewed_tickets: Set[Tuple[str, str]] = set()

    def start(self) -> None:
        threading.Thread(target=self._planning_loop, daemon=True).start()
        threading.Thread(target=self._implementation_loop, daemon=True).start()

    def stop(self) -> None:
        self.stop_event.set()

    def state(self) -> Dict:
        with self.impl_lock:
            active = self.active_impl_ticket
            started = self.active_impl_started
        return {
            "active_impl_ticket": {
                "project_id": active[0],
                "work_item_id": active[1],
                "started_at": started,
            }
            if active
            else None,
            "planned_count": len(self.planned_tickets),
            "review_ready_count": len(self.reviewed_tickets),
        }

    def _planning_loop(self) -> None:
        while not self.stop_event.is_set():
            self.metrics.inc("planning_poll_cycles")
            for project_id in self.cfg.plane_project_ids:
                try:
                    self._process_planning_project(project_id)
                except Exception:
                    self.metrics.inc("planning_errors")
                    self.log.exception("Planning loop failure for project=%s", project_id)
            self.stop_event.wait(self.cfg.poll_seconds)

    def _implementation_loop(self) -> None:
        while not self.stop_event.is_set():
            self.metrics.inc("implementation_poll_cycles")
            try:
                self._process_implementation_once()
            except Exception:
                self.metrics.inc("implementation_errors")
                self.log.exception("Implementation loop failure")
            self.stop_event.wait(self.cfg.poll_seconds)

    def _process_planning_project(self, project_id: str) -> None:
        state_ids = self._load_state_ids(project_id)
        planning_name = self.cfg.plane_state_planning
        required_label = self.cfg.plane_label_needs_plan.lower()

        for item in self.plane.list_work_items(project_id):
            work_item_id = str(item.get("id", ""))
            if not work_item_id:
                continue
            key = (project_id, work_item_id)
            if key in self.planned_tickets:
                continue

            state_name = self.plane.item_state_name(item).lower()
            labels = {name.lower() for name in self.plane.item_label_names(item)}
            if state_name != planning_name.lower() or required_label not in labels:
                continue

            plan_text = self._build_plan_text(item)
            comment = self._html_from_markdown(plan_text)
            self.plane.add_comment(project_id, work_item_id, comment)
            planned_state = state_ids.get(self.cfg.plane_state_planned.lower())
            if planned_state:
                self.plane.update_work_item_state(project_id, work_item_id, planned_state)
            self.planned_tickets.add(key)
            self.metrics.inc("planning_plans_posted")
            self.log.info("Posted plan for %s/%s", project_id, work_item_id)

    def _process_implementation_once(self) -> None:
        with self.impl_lock:
            if self.active_impl_ticket is not None:
                self.log.info("Implementation already active for %s", self.active_impl_ticket)
                return

        candidates: List[Tuple[str, Dict]] = []
        required_state = self.cfg.plane_state_implement.lower()
        required_label = self.cfg.plane_label_ready_for_impl.lower()

        for project_id in self.cfg.plane_project_ids:
            for item in self.plane.list_work_items(project_id):
                work_item_id = str(item.get("id", ""))
                if not work_item_id:
                    continue

                state_name = self.plane.item_state_name(item).lower()
                labels = {name.lower() for name in self.plane.item_label_names(item)}
                if state_name == required_state and required_label in labels:
                    candidates.append((project_id, item))

        if not candidates:
            return

        candidates.sort(key=lambda pair: str(pair[1].get("created_at", "")))
        project_id, item = candidates[0]
        work_item_id = str(item["id"])

        with self.impl_lock:
            self.active_impl_ticket = (project_id, work_item_id)
            self.active_impl_started = datetime.now(timezone.utc).isoformat()

        try:
            self._implement_item(project_id, item)
        finally:
            with self.impl_lock:
                self.active_impl_ticket = None
                self.active_impl_started = None

    def _implement_item(self, project_id: str, item: Dict) -> None:
        work_item_id = str(item["id"])
        key = (project_id, work_item_id)
        if key in self.reviewed_tickets:
            return

        repo = self.cfg.repo_for_project(project_id)
        if not repo:
            self.log.warning("Skipping implementation for %s/%s: no GitHub repo mapping", project_id, work_item_id)
            return

        repo_info = self.github.get_repo_info(repo)
        default_branch = str(repo_info.get("default_branch", "main"))
        base_sha = self.github.get_ref_sha(repo, default_branch)

        safe_slug = self._slug(str(item.get("name") or item.get("title") or work_item_id))
        branch = f"feature/{work_item_id[:8]}-{safe_slug}"
        self.github.ensure_branch(repo, branch, base_sha)

        automation_path = f"{self.cfg.automation_file_prefix}/{work_item_id}.md"
        automation_md = self._build_automation_file(item, project_id, repo)
        self.github.put_text_file(
            repo=repo,
            branch=branch,
            path=automation_path,
            content=automation_md,
            message=f"chore(openclaw): scaffold automation notes for {work_item_id}",
        )

        title = str(item.get("name") or item.get("title") or f"Work Item {work_item_id}")
        pr_body = (
            f"Automated implementation ticket for Plane work item `{work_item_id}`.\n\n"
            f"- Project ID: `{project_id}`\n"
            f"- Source workflow: OpenClaw implementation mode\n"
            f"- Generated artifact: `{automation_path}`\n"
        )

        existing_pr = self.github.find_open_pr(repo, branch)
        pr = existing_pr or self.github.create_pr(
            repo=repo,
            title=f"[OpenClaw] {title}",
            body=pr_body,
            head=branch,
            base=default_branch,
        )
        pr_url = str(pr.get("html_url", "")).strip()

        state_ids = self._load_state_ids(project_id)
        review_state_id = state_ids.get(self.cfg.plane_state_review.lower())
        if pr_url:
            comment = self._html_from_markdown(
                f"### OpenClaw Implementation\n\nPR created: {pr_url}\n"
            )
            self.plane.add_comment(project_id, work_item_id, comment)
        if review_state_id and pr_url:
            self.plane.update_work_item_state(project_id, work_item_id, review_state_id)
        self.reviewed_tickets.add(key)
        self.metrics.inc("implementation_prs_created")
        self.log.info("Moved %s/%s to Review with PR %s", project_id, work_item_id, pr_url)

    def _load_state_ids(self, project_id: str) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for state in self.plane.list_states(project_id):
            name = str(state.get("name", "")).strip().lower()
            state_id = str(state.get("id", "")).strip()
            if name and state_id:
                mapping[name] = state_id
        return mapping

    @staticmethod
    def _slug(value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
        if not slug:
            return "ticket"
        return slug[:40]

    @staticmethod
    def _build_plan_text(item: Dict) -> str:
        ticket_id = str(item.get("id", "unknown"))
        title = str(item.get("name") or item.get("title") or "Untitled")
        description = str(item.get("description_html") or item.get("description_stripped") or "")
        return (
            f"## OpenClaw Plan for {ticket_id}\n\n"
            f"### Problem\n{title}\n\n"
            f"### Scope\n"
            f"- Implement only what is required for this ticket.\n"
            f"- Keep changes minimal and testable.\n\n"
            f"### Approach\n"
            f"1. Reproduce current behavior and define acceptance checks.\n"
            f"2. Implement the smallest coherent change set.\n"
            f"3. Add or update tests covering new behavior.\n"
            f"4. Open PR with concise summary and validation evidence.\n\n"
            f"### Known Context\n{description or 'No additional description provided.'}\n\n"
            f"### Risks\n"
            f"- Hidden dependencies across projects.\n"
            f"- Incomplete ticket details may require engineer clarification.\n"
        )

    @staticmethod
    def _build_automation_file(item: Dict, project_id: str, repo: str) -> str:
        ticket_id = str(item.get("id", "unknown"))
        title = str(item.get("name") or item.get("title") or "Untitled")
        now = datetime.now(timezone.utc).isoformat()
        return (
            f"# OpenClaw Automation Artifact\n\n"
            f"- Timestamp: {now}\n"
            f"- Plane Project: {project_id}\n"
            f"- Plane Work Item: {ticket_id}\n"
            f"- GitHub Repo: {repo}\n\n"
            f"## Ticket\n{title}\n\n"
            f"## Next Step\nEngineer review required. Replace this scaffold with real implementation changes.\n"
        )

    @staticmethod
    def _html_from_markdown(text: str) -> str:
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"<pre>{safe}</pre>"

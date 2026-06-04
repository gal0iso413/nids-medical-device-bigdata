import json
import os

import requests

GENERAL_CHANNEL_NAME = "#overall_project"


class AgentSlacker:
    """
    Mandatory communication layer for the multi-agent system.
    Outbound-only: agents post to Slack; the PM issues all commands in Cursor Composer.
    No Slack-to-code listener is implemented or permitted.
    """

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.agent_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.general_webhook_url = os.getenv("SLACK_GENERAL_WEBHOOK_URL")

    def _post(self, webhook_url: str | None, payload: dict) -> None:
        if not webhook_url:
            return
        requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

    def escalate_roadblock(
        self,
        issue_title: str,
        context_dump: str,
        agent_counter_argument: str,
        *,
        broadcast_global: bool = False,
    ) -> None:
        """
        Severe block: agent channel always; optional mirror to #general-pm-board.
        HALT until PM unblocks via Composer (not via Slack replies).
        """
        payload = {
            "text": f"🚨 *[ROADBLOCK ESCALATION]* from Project Leader: `{self.agent_name}`",
            "attachments": [
                {
                    "color": "#FF0000",
                    "fields": [
                        {"title": "Issue Detected", "value": issue_title, "short": True},
                        {"title": "Data Context Snapshot", "value": context_dump, "short": False},
                        {
                            "title": "Agent's Technical Counter-Argument",
                            "value": agent_counter_argument,
                            "short": False,
                        },
                    ],
                    "footer": "State: HALTED. PM must respond in Cursor Composer (not Slack).",
                }
            ],
        }
        self._post(self.agent_webhook_url, payload)
        if broadcast_global:
            global_payload = {
                "text": f"🚨 *[GLOBAL ROADBLOCK]* `{self.agent_name}` → {GENERAL_CHANNEL_NAME}",
                "attachments": payload["attachments"],
            }
            self._post(self.general_webhook_url, global_payload)

    def notify_phase_completion(
        self,
        phase_name: str,
        analytical_insights: str,
        *,
        broadcast_global: bool = False,
    ) -> None:
        """
        Phase milestone complete on the agent's project channel.
        Optional broadcast_global for discoveries that affect all agents.
        """
        payload = {
            "text": f"✅ *[PHASE COMPLETED]* by Project Leader: `{self.agent_name}`",
            "attachments": [
                {
                    "color": "#36a64f",
                    "fields": [
                        {"title": "Milestone", "value": phase_name, "short": True},
                        {
                            "title": "Analytical Summary & Discovery",
                            "value": analytical_insights,
                            "short": False,
                        },
                    ],
                    "footer": "State: IDLE. PM must issue next phase in Cursor Composer (not Slack).",
                }
            ],
        }
        self._post(self.agent_webhook_url, payload)
        if broadcast_global:
            global_payload = {
                "text": f"✅ *[GLOBAL SYNC]* `{self.agent_name}` → {GENERAL_CHANNEL_NAME}",
                "attachments": payload["attachments"],
            }
            self._post(self.general_webhook_url, global_payload)

    def broadcast_global_sync(self, subject: str, message: str) -> None:
        """
        Central orchestration channel for cross-agent synchronization:
        global parameter changes, shared discoveries, systemic constraints.
        """
        if not self.general_webhook_url:
            return
        payload = {
            "text": f"📡 *[GLOBAL SYNC]* {GENERAL_CHANNEL_NAME} — from `{self.agent_name}`",
            "attachments": [
                {
                    "color": "#439FE0",
                    "fields": [
                        {"title": "Subject", "value": subject, "short": True},
                        {"title": "Message", "value": message, "short": False},
                    ],
                    "footer": "PM commands and approvals remain in Cursor Composer only.",
                }
            ],
        }
        self._post(self.general_webhook_url, payload)

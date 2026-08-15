import json

from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import TemplateView

from ai_agent.domain.service.game import GameService
from ai_agent.domain.service.game_agent import GameAgentService
from ai_agent.domain.service.skill_tools import GameToolSet, SkillToolCatalog
from ai_agent.domain.valueobject.agent_execution import AgentRunStatus


class IndexView(TemplateView):
    """敵選択、セリフ決定、Agent実行を扱うゲーム画面アダプター。"""

    template_name = "ai_agent/index.html"
    state_cookie_name = "ai_agent_game_state"

    def get_context_data(self, **kwargs):
        """現在のゲーム状態と画面操作に必要なSkill定義を渡す。"""
        context = super().get_context_data(**kwargs)
        game = self._load_state()
        context["game"] = game
        context["skill_tools"] = SkillToolCatalog.definitions()
        context["selected_enemy"] = (
            game.enemy(game.selected_enemy_id) if game.selected_enemy_id else None
        )
        return context

    def post(self, request, *args, **kwargs):
        """画面操作をドメインサービスへ渡し、署名付きCookieへ状態を保存する。"""
        game = self._load_state()
        action = request.POST.get("action")
        try:
            if action == "select_enemy":
                game = GameService.select_enemy(game, request.POST["enemy_id"])
                messages.success(
                    request, "対象の敵を選択しました。次にセリフを選んでください。"
                )
            elif action == "select_line":
                if not game.selected_enemy_id:
                    raise ValueError("先に対象の敵を選択してください")
                game = GameService.select_line(game, request.POST["line_id"])
                game, run = self._run_agent(game)
                self._add_agent_message(request, game, run)
            elif action == "reset":
                game = GameService.create_game()
                messages.success(request, "ゲームを初期状態へ戻しました。")
            else:
                raise ValueError("unknown game action")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            messages.error(request, f"操作できません: {error}")

        response = redirect("agt:index")
        response.set_signed_cookie(
            self.state_cookie_name,
            game.to_json(),
            httponly=True,
            samesite="Lax",
        )
        return response

    def _load_state(self):
        """署名付きCookieから状態を読み、壊れていれば初期状態へ戻す。"""
        raw_state = self.request.get_signed_cookie(self.state_cookie_name, default=None)
        if raw_state is None:
            return GameService.create_game()
        try:
            return GameService.create_game().from_json(raw_state)
        except (TypeError, ValueError, json.JSONDecodeError):
            return GameService.create_game()

    @staticmethod
    def _run_agent(game):
        """選択状態をAgentへ渡し、Agent実行後のTool状態を返す。"""
        tools = GameToolSet(game)
        agent = GameAgentService(tools=tools)
        run = agent.run_selected()
        return tools.state, run

    @staticmethod
    def _add_agent_message(request, game, run):
        """AgentのTool選択結果または実行失敗を画面通知へ変換する。"""
        if run.status is AgentRunStatus.COMPLETED:
            tool_names = [tool.name for tool in run.tool_calls]
            tool_summary = "、".join(tool_names) if tool_names else "Toolなし"
            messages.success(
                request,
                f"Agentが {tool_summary} を選択・実行しました。"
                f"経験値は {game.experience} です。",
            )
        else:
            messages.error(request, f"Agent実行に失敗しました: {run.report.error}")

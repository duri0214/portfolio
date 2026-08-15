import json

from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import TemplateView

from ai_agent.domain.service.game import GameService
from ai_agent.domain.service.skill_tools import SkillToolCatalog


class IndexView(TemplateView):
    """敵選択、セリフ選択、Skill実行を扱うゲーム画面アダプター。"""

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
                game = GameService.select_line(game, request.POST["line_id"])
                messages.success(
                    request, "セリフを選択しました。相性のよいSkillを実行できます。"
                )
            elif action == "use_tool":
                game, result = self._execute_tool(game, request)
                messages.success(request, result.message)
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
    def _execute_tool(game, request):
        """選択済みの敵へ、指定されたSkillを1回適用する。"""
        if not game.selected_enemy_id:
            raise ValueError("先に対象の敵を選択してください")
        score = int(request.POST.get("score", "0"))
        definition = SkillToolCatalog.get(request.POST["tool_name"])
        return GameService.execute_skill(
            game,
            definition,
            target_enemy_id=game.selected_enemy_id,
            score=score,
        )

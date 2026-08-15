from django.views.generic import TemplateView

from ai_agent.domain.service.game import GameService
from ai_agent.domain.service.skill_tools import SkillToolCatalog


class IndexView(TemplateView):
    """ゲームドメインの初期状態を表示する薄いDjangoアダプター。"""

    template_name = "ai_agent/index.html"

    def get_context_data(self, **kwargs):
        """初期ゲーム状態とAgentが利用できるSkill定義をテンプレートへ渡す。"""
        context = super().get_context_data(**kwargs)
        context["game"] = GameService.create_game()
        context["skill_tools"] = SkillToolCatalog.definitions()
        return context

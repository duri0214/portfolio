import asyncio
from dataclasses import asdict, replace
from hashlib import sha256
import json
from uuid import uuid4

from django.contrib import messages
from django.core import signing
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView

from ai_agent.domain.service.game import GameService
from ai_agent.domain.service.game_agent import GameAgentService
from ai_agent.domain.service.skill_tools import GameToolSet
from ai_agent.domain.valueobject.agent_execution import AgentRunStatus
from ai_agent.domain.valueobject.game import (
    AgentExecutionRecord,
    BoardEventRecord,
    Position,
)


class IndexView(TemplateView):
    """問題選択、セリフ決定、Agent実行を扱うゲーム画面アダプター。"""

    template_name = "ai_agent/index.html"
    state_cookie_name = "ai_agent_game_state"
    execution_history_session_key = "ai_agent_execution_history"
    board_event_history_session_key = "ai_agent_board_event_history"
    stream_pending_session_key = "ai_agent_pending_stream_state"
    stream_state_salt = "ai_agent.stream_state"

    def get_context_data(self, **kwargs):
        """現在のゲーム状態と画面操作に必要なSkill定義を渡す。"""
        context = super().get_context_data(**kwargs)
        game = self._load_state()
        context["game"] = game
        context["selected_mondai"] = (
            game.mondai(game.selected_mondai_id) if game.selected_mondai_id else None
        )
        context["board_cells"] = self._board_cells(game)
        return context

    def post(self, request, *args, **kwargs):
        """画面操作をドメインサービスへ渡し、状態を保存する。"""
        game = self._load_state()
        action = request.POST.get("action")
        try:
            if action == "select_mondai":
                game = GameService.select_mondai(game, request.POST["mondai_id"])
                messages.success(
                    request, "対象の問題を選択しました。次にセリフを選んでください。"
                )
            elif action == "select_board_space":
                game = GameService.select_board_space(game, request.POST["space_id"])
                event = game.board_event_history[0]
                messages.success(
                    request,
                    f"{event.space_name}へ移動しました。{event.summary}",
                )
            elif action == "stream_agent":
                if not game.selected_mondai_id:
                    raise ValueError("先に対象の問題を選択してください")
                base_state = game
                game = GameService.select_line(game, request.POST["line_id"])
                return self._stream_agent_response(game, base_state)
            elif action == "save_stream_state":
                payload = self._unsign_stream_state(request.POST["state_token"])
                self._consume_stream_state(payload)
                game = GameService.create_game().from_json(payload["state"])
                self._add_saved_agent_message(request, game)
                response = redirect("agt:index")
                self._set_game_cookie(response, game)
                return response
            elif action == "select_line":
                if not game.selected_mondai_id:
                    raise ValueError("先に対象の問題を選択してください")
                game = GameService.select_line(game, request.POST["line_id"])
                game, run = self._run_agent(game)
                game = game.with_execution_record(
                    GameAgentService.create_execution_record(game, run)
                )
                self._add_agent_message(request, game, run)
            elif action == "reset":
                game = GameService.create_game()
                messages.success(request, "ゲームを初期状態へ戻しました。")
            else:
                raise ValueError("unknown game action")
        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            signing.BadSignature,
        ) as error:
            if (
                action == "save_stream_state"
                and request.headers.get("Accept") == "application/json"
            ):
                return JsonResponse({"error": str(error)}, status=409)
            messages.error(request, f"操作できません: {error}")

        response = redirect("agt:index")
        self._set_game_cookie(response, game)
        return response

    def _stream_agent_response(self, game, base_state):
        """AgentのToolイベントをSSEで逐次配信する。"""
        tools = GameToolSet(game)
        agent = GameAgentService(tools=tools)
        token_id = uuid4().hex
        base_state_digest = self._state_fingerprint(base_state)
        self.request.session[self.stream_pending_session_key] = {
            "token_id": token_id,
            "base_state": base_state_digest,
        }

        def event_stream():
            loop = asyncio.new_event_loop()
            iterator = agent.stream_selected()
            try:
                while True:
                    try:
                        event = loop.run_until_complete(anext(iterator))
                    except StopAsyncIteration:
                        break
                    payload = {
                        key: value for key, value in event.items() if key != "run"
                    }
                    if event["type"] == "report.completed":
                        final_state = tools.state.with_execution_record(
                            GameAgentService.create_execution_record(
                                tools.state, event["run"]
                            )
                        )
                        payload["state_token"] = self._sign_stream_state(
                            final_state, token_id, base_state_digest
                        )
                    yield self._sse(payload)
            finally:
                try:
                    loop.run_until_complete(iterator.aclose())
                finally:
                    loop.close()

        response = StreamingHttpResponse(
            event_stream(), content_type="text/event-stream; charset=utf-8"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    @staticmethod
    def _sse(payload):
        return f"event: {payload['type']}\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"

    def _sign_stream_state(self, game, token_id, base_state_digest):
        payload = json.dumps(
            {
                "state": game.to_json(),
                "token_id": token_id,
                "base_state": base_state_digest,
            },
            separators=(",", ":"),
        )
        return signing.Signer(salt=self.stream_state_salt).sign(payload)

    def _unsign_stream_state(self, value):
        payload = json.loads(signing.Signer(salt=self.stream_state_salt).unsign(value))
        if not isinstance(payload, dict) or not all(
            isinstance(payload.get(key), str)
            for key in ("state", "token_id", "base_state")
        ):
            raise ValueError("ストリーム状態Tokenの形式が不正です")
        return payload

    @staticmethod
    def _state_fingerprint(game):
        state_without_history = replace(
            game,
            execution_history=(),
            board_event_history=(),
        )
        return sha256(state_without_history.to_json().encode("utf-8")).hexdigest()

    def _consume_stream_state(self, payload):
        pending = self.request.session.get(self.stream_pending_session_key)
        if not isinstance(pending, dict) or any(
            pending.get(key) != payload[key] for key in ("token_id", "base_state")
        ):
            raise ValueError("ストリーム状態Tokenは期限切れか、すでに使用されています")

        self.request.session.pop(self.stream_pending_session_key, None)
        current_state = self._load_state()
        if self._state_fingerprint(current_state) != payload["base_state"]:
            raise ValueError(
                "ゲーム状態が更新されています。画面を再読み込みしてください"
            )

    def _set_game_cookie(self, response, game):
        self._save_execution_history(game)
        self._save_board_event_history(game)
        cookie_game = replace(
            game,
            execution_history=(),
            board_event_history=(),
        )
        response.set_signed_cookie(
            self.state_cookie_name,
            cookie_game.to_json(),
            httponly=True,
            samesite="Lax",
        )

    def _load_state(self):
        """Cookieとセッションから状態を読み、壊れていれば初期状態へ戻す。"""
        raw_state = self.request.get_signed_cookie(self.state_cookie_name, default=None)
        if raw_state is None:
            game = GameService.create_game()
        else:
            try:
                game = GameService.create_game().from_json(raw_state)
            except (TypeError, ValueError, json.JSONDecodeError):
                game = GameService.create_game()
        history = self._load_execution_history()
        board_event_history = self._load_board_event_history()
        updates = {}
        if history is not None:
            updates["execution_history"] = history
        if board_event_history is not None:
            updates["board_event_history"] = board_event_history
        return replace(game, **updates) if updates else game

    def _load_execution_history(self):
        """セッションに保存した実行履歴を画面表示用の値へ復元する。"""
        payload = self.request.session.get(self.execution_history_session_key)
        if payload is None:
            return None
        return tuple(
            AgentExecutionRecord.from_dict(record)
            for record in payload
            if isinstance(record, dict)
        )

    def _save_execution_history(self, game):
        """Cookie上限を避けるため、増え続ける履歴をセッションへ保存する。"""
        if game.execution_history:
            self.request.session[self.execution_history_session_key] = [
                asdict(record) for record in game.execution_history
            ]
        else:
            self.request.session.pop(self.execution_history_session_key, None)

    def _load_board_event_history(self):
        """セッションに保存した盤面イベント履歴を復元する。"""
        payload = self.request.session.get(self.board_event_history_session_key)
        if payload is None:
            return None
        return tuple(
            BoardEventRecord.from_dict(record)
            for record in payload
            if isinstance(record, dict)
        )

    def _save_board_event_history(self, game):
        """Cookie上限を避けるため、盤面イベント履歴をセッションへ保存する。"""
        if game.board_event_history:
            self.request.session[self.board_event_history_session_key] = [
                asdict(record) for record in game.board_event_history
            ]
        else:
            self.request.session.pop(self.board_event_history_session_key, None)

    @staticmethod
    def _board_cells(game):
        """CSS Gridへ渡す盤面の各マスと駒の情報を作る。"""
        problems_by_position = {
            (problem.position.row, problem.position.column): problem
            for problem in game.mondais
        }
        spaces_by_position = {
            (space.position.row, space.position.column): space
            for space in game.board_spaces
        }
        return [
            {
                "row": row,
                "column": column,
                "is_player": game.player_position == Position(row, column),
                "problem": problems_by_position.get((row, column)),
                "special_space": spaces_by_position.get((row, column)),
                "special_space_used": (
                    spaces_by_position.get((row, column)) is not None
                    and spaces_by_position[(row, column)].space_id
                    in game.used_board_space_ids
                ),
            }
            for row in range(game.board_size)
            for column in range(game.board_size)
        ]

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
            messages.success(
                request,
                f"Agentが処理を完了しました。経験値は {game.experience} です。"
                "下の実行履歴で判断と結果を確認できます。",
            )
        else:
            messages.error(request, f"Agent実行に失敗しました: {run.report.error}")

    @staticmethod
    def _add_saved_agent_message(request, game):
        """保存済みのストリーミング実行結果を画面通知へ変換する。"""
        if not game.execution_history:
            return
        record = game.execution_history[0]
        if record.status == AgentRunStatus.COMPLETED.value:
            messages.success(
                request,
                f"Agentが{len(record.steps)}つのSkillをチェーンしました。結果を反映しました。",
            )
        else:
            messages.error(
                request,
                f"Agent実行に失敗しました: {record.error or '実行結果を確認できませんでした。'}",
            )

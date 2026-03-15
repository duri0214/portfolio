from llm_chat.domain.valueobject.completion.riddle import Riddle
from llm_chat.models import RiddleQuestion


class RiddleQuestionRepository:
    """
    なぞなぞの問題を管理するリポジトリ。
    """

    @staticmethod
    def fetch_all() -> list[Riddle]:
        """
        DBからなぞなぞの問題セットを取得し、Riddle オブジェクトのリストとして返します。

        Returns:
            list[Riddle]: なぞなぞ問題のリスト。
        """
        db_questions = RiddleQuestion.objects.all().order_by("order")
        return [
            Riddle(question=q.question_text, answer=q.answer_text) for q in db_questions
        ]

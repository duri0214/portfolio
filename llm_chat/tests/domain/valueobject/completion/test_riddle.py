from django.test import TestCase
from pydantic import ValidationError
from llm_chat.domain.valueobject.completion.riddle import RiddleEvaluation


class RiddleEvaluationTest(TestCase):
    def test_total_score_calculation(self):
        """
        シナリオ:
        - 入力: 正確性: 3, 論理: 4, 独創性: 2, 反論: 0 の評価データ。
        - 処理: total_score プロパティを呼び出す。
        - 期待値: 合計値 9 が返されること。
        """
        # Given
        eval_obj = RiddleEvaluation(
            correctness=3,
            reasoning=4,
            creativity=2,
            rebuttal=0,
            comment="論理は弱いが発想は面白い",
        )

        # When
        total = eval_obj.total_score

        # Then
        self.assertEqual(total, 9)

    def test_validation_success(self):
        """
        シナリオ:
        - 入力: すべてのフィールドが許容範囲内のデータ（例: 全て最大値）。
        - 処理: RiddleEvaluation インスタンスを作成する。
        - 期待値: バリデーションエラーが発生せずにインスタンスが作成されること。
        """
        # Given / When
        try:
            RiddleEvaluation(
                correctness=5,
                reasoning=5,
                creativity=5,
                rebuttal=3,
                comment="完璧な回答",
            )
        except ValidationError:
            # Then
            self.fail("ValidationError raised unexpectedly")

    def test_validation_error_correctness_out_of_range(self):
        """
        シナリオ:
        - 入力: correctness が 6 (許容範囲 0-5 を超える)。
        - 処理: RiddleEvaluation インスタンスを作成する。
        - 期待値: ValidationError が発生すること。
        """
        # Given / When / Then
        with self.assertRaises(ValidationError):
            RiddleEvaluation(
                correctness=6, reasoning=0, creativity=0, rebuttal=0, comment="error"
            )

    def test_validation_error_rebuttal_out_of_range(self):
        """
        シナリオ:
        - 入力: rebuttal が 4 (許容範囲 0-3 を超える)。
        - 処理: RiddleEvaluation インスタンスを作成する。
        - 期待値: ValidationError が発生すること。
        """
        # Given / When / Then
        with self.assertRaises(ValidationError):
            RiddleEvaluation(
                correctness=0, reasoning=0, creativity=0, rebuttal=4, comment="error"
            )

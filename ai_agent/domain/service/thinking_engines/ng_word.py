class NGWordService:
    @staticmethod
    def can_respond(input_text, entity):
        """
        禁止ワードに基づいてエンティティが応答できるかどうかを判定します。

        Args:
            input_text (str): チェック対象の入力テキスト
            entity (Entity): 評価対象のエンティティ

        Returns:
            bool: 禁止ワードが検出されなかった場合はTrue、そうでなければFalse
        """
        try:
            # GuardrailConfigから禁止ワードを取得
            guardrail_config = entity.guardrailconfig
            forbidden_list = guardrail_config.forbidden_words
            if forbidden_list and any(
                keyword in input_text for keyword in forbidden_list
            ):
                return False
        except AttributeError:
            print("GuardrailConfigがありませんでした")
        return True

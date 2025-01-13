class NGWordService:
    @staticmethod
    def can_respond(input_text, entity):
        """
        Determine if the entity can respond based on forbidden keywords.

        Args:
            input_text (str): The input text to check.
            entity (Entity): The entity being evaluated.

        Returns:
            bool: True if no forbidden keywords are detected, otherwise False.
        """
        if entity.forbidden_keywords:
            forbidden_list = entity.forbidden_keywords.split(",")
            if any(keyword in input_text for keyword in forbidden_list):
                return False
        return True

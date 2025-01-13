class GoogleMapsReviewService:
    @staticmethod
    def can_respond(input_text: str, entity) -> bool:
        """
        Determines if the entity can respond based on Google Maps reviews.

        TODO: Implement proper review-based logic.

        Args:
            input_text (str): The input text to evaluate.
            entity (Entity): The entity performing the evaluation.

        Returns:
            bool: Always True for now (temporarily hardcoded for testing purposes).
        """
        return True

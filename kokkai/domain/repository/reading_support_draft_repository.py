from ...models import (
    ReadingSupportDraft,
    ReadingSupportDraftCandidate,
    ReadingSupportEntry,
)


class ReadingSupportDraftRepository:
    """読み仮名支援辞書の下書きと候補の永続化を担当する。"""

    def create_draft(
        self,
        *,
        source_url: str,
        source_text: str,
        model_name: str,
        created_by=None,
    ) -> ReadingSupportDraft:
        """候補生成の下書きを保存する。"""
        return ReadingSupportDraft.objects.create(
            source_url=source_url,
            source_text=source_text,
            model_name=model_name,
            created_by=created_by,
        )

    def create_candidate(
        self,
        draft: ReadingSupportDraft,
        *,
        entry_type: str,
        surface: str,
        reading: str,
        description: str,
        category: str,
        source_url: str,
        needs_review: bool,
        review_note: str,
    ) -> ReadingSupportDraftCandidate:
        """下書きへ辞書候補を保存する。"""
        return ReadingSupportDraftCandidate.objects.create(
            draft=draft,
            entry_type=entry_type,
            surface=surface,
            reading=reading,
            description=description,
            category=category,
            source_url=source_url,
            needs_review=needs_review,
            review_note=review_note,
        )

    def list_approved_unregistered_candidates(
        self, draft: ReadingSupportDraft
    ) -> list[ReadingSupportDraftCandidate]:
        """登録承認済みで、まだ登録していない候補を返す。"""
        return list(
            draft.candidates.filter(is_approved=True, is_registered=False).order_by(
                "pk"
            )
        )

    def mark_candidate_registered(
        self,
        candidate: ReadingSupportDraftCandidate,
        entry: ReadingSupportEntry,
    ) -> None:
        """候補を登録済みとして登録先とともに保存する。"""
        candidate.is_registered = True
        candidate.needs_review = False
        candidate.registered_entry = entry
        candidate.save(
            update_fields=[
                "is_registered",
                "needs_review",
                "registered_entry",
                "updated_at",
            ]
        )

    def mark_imported(self, draft: ReadingSupportDraft) -> None:
        """下書きを登録済みとして保存する。"""
        draft.status = ReadingSupportDraft.Status.IMPORTED
        draft.error_message = ""
        draft.save(update_fields=["status", "error_message", "updated_at"])

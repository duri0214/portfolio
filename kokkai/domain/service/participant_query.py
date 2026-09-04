from ...models import Meeting
from ..repository.participant_repository import MeetingParticipantRepository
from ..valueobject.participant import ParticipantActorData


class ParticipantQueryService:
    """会議参加者の一覧表示とシナリオ連携用の読み取りを担当する。"""

    def __init__(self, repository: MeetingParticipantRepository | None = None) -> None:
        self.repository = repository or MeetingParticipantRepository()

    def list_participants(self, meeting: Meeting):
        """根拠を含む会議参加者一覧を返す。"""

        return self.repository.list_for_meeting(meeting)

    def get_actor_candidates(self, meeting: Meeting) -> list[ParticipantActorData]:
        """発言者を先に並べたアクター候補を返す。"""

        return self.repository.get_actor_candidates(meeting)

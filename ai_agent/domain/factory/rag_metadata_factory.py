from ai_agent.domain.valueobject.context_analyzer import (
    RagMetadataBase,
    GoogleMapsMetadata,
    PdfSourceMetadata,
)


class RagMetadataFactory:
    _METADATA_CLASSES: dict[str, type[RagMetadataBase]] = {
        "google_maps_based": GoogleMapsMetadata,
        "cloud_act_based": PdfSourceMetadata,
        "declining_birth_rate_based": PdfSourceMetadata,
    }

    @classmethod
    def create(cls, material_type: str, metadata_dict: dict) -> RagMetadataBase:
        """
        material_typeに応じた適切なメタデータValue Objectを作成

        Args:
            material_type: RagMaterial.material_type
            metadata_dict: メタデータの辞書

        Returns:
            対応するValue Objectインスタンス

        Raises:
            ValueError: 未対応のmaterial_type
            KeyError: 必要なキーが辞書に含まれていない
        """
        if material_type not in cls._METADATA_CLASSES:
            raise ValueError(f"Unsupported material_type: {material_type}")

        metadata_class = cls._METADATA_CLASSES[material_type]
        return metadata_class.from_dict(metadata_dict)

    @classmethod
    def get_supported_types(cls) -> list[str]:
        """サポートされているmaterial_typeの一覧を取得"""
        return list(cls._METADATA_CLASSES.keys())

import csv
import os
from dataclasses import dataclass
from datetime import datetime

import pytz


@dataclass(frozen=True)
class HardnessRow:
    """
    土壌硬度データをパースしたデータ行

    Attributes:
        set_device_name: デバイス名
        set_memory: メモリー番号
        set_datetime: 測定日時
        set_depth: 設定深度
        set_spring: スプリング番号
        set_cone: コーン番号
        depth: 測定深度
        pressure: 圧力
        folder: フォルダ名
        file_name: ファイル名
    """

    set_device_name: str
    set_memory: int
    set_datetime: datetime
    set_depth: int
    set_spring: int
    set_cone: int
    depth: int
    pressure: int
    folder: str
    file_name: str


class HardnessImportParser:
    """
    土壌硬度CSVファイルのパースを担当する
    """

    @staticmethod
    def _validate_label(
        line: list,
        expected_labels: str | tuple[str, ...],
        is_prefix: bool = False,
        label_index: int = 0,
        value_index: int = 1,
    ) -> str:
        label = line[label_index].strip()
        if isinstance(expected_labels, str):
            if is_prefix:
                if not label.startswith(expected_labels):
                    raise ValueError(f"unexpected data row: {label}")
            else:
                if label != expected_labels:
                    raise ValueError(f"unexpected data row: {label}")
        else:
            if not any(label.startswith(prefix) for prefix in expected_labels):
                raise ValueError(f"unexpected data row: {label}")
        return line[value_index].strip()

    @classmethod
    def extract_device(cls, line: list) -> str:
        cls._validate_label(
            line,
            expected_labels="Digital Cone Penetrometer",
            label_index=1,
        )
        return cls._validate_label(
            line, expected_labels="DIK-", is_prefix=True, value_index=0
        )

    @classmethod
    def extract_datetime(cls, line: list) -> datetime:
        value = cls._validate_label(line, "Date and Time")
        try:
            return pytz.timezone("Asia/Tokyo").localize(
                datetime.strptime(value, "%y.%m.%d %H:%M:%S")
            )
        except ValueError:
            raise ValueError(f"unexpected datetime: {value}")

    @classmethod
    def extract_numeric_value(cls, line: list) -> int:
        value = cls._validate_label(line, ("Memory No.", "Set Depth", "Spring", "Cone"))
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"unexpected numeric value: {value}")

    @classmethod
    def parse_csv(cls, file_path: str) -> list[HardnessRow]:
        """
        CSVファイルをパースしてHardnessRowのリストを返す
        """
        rows = []
        parent_folder = os.path.basename(os.path.dirname(file_path))
        file_name = os.path.basename(file_path)

        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)

            # 1行目～10行目 から属性情報を取得
            set_device_name = cls.extract_device(next(reader))
            set_memory = cls.extract_numeric_value(next(reader))
            next(reader)  # skip Latitude
            next(reader)  # skip Longitude
            set_depth = cls.extract_numeric_value(next(reader))
            set_datetime = cls.extract_datetime(next(reader))
            set_spring = cls.extract_numeric_value(next(reader))
            set_cone = cls.extract_numeric_value(next(reader))
            next(reader)  # skip blank line
            next(reader)  # skip header line

            # 11行目以降のデータをパース
            for row in reader:
                rows.append(
                    HardnessRow(
                        set_device_name=set_device_name,
                        set_memory=set_memory,
                        set_datetime=set_datetime,
                        set_depth=set_depth,
                        set_spring=set_spring,
                        set_cone=set_cone,
                        depth=int(row[0]),
                        pressure=int(row[1]),
                        folder=parent_folder,
                        file_name=file_name,
                    )
                )
        return rows

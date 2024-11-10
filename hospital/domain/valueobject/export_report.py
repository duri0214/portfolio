from dataclasses import dataclass
from datetime import datetime

from django.db import models


@dataclass
class DataRow:
    fields: list[models.Field]
    instance: models.Model

    def to_list(self):
        # TODO: 具体的に請求者名簿の型、不在者投票事務処理簿の型にしよう
        row = []
        for field in self.fields:
            if isinstance(field, models.ForeignKey):
                value = getattr(self.instance, f"{field.name}_id")
                if isinstance(value, datetime):
                    value = value.replace(tzinfo=None)
            else:
                value = getattr(self.instance, field.name)
                if isinstance(value, datetime):
                    value = value.replace(tzinfo=None)
            row.append(value)
        return row

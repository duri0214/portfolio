from abc import ABC, abstractmethod


class XbrlBase(ABC):
    def __init__(self):
        pass  # TODO

    @abstractmethod
    def to_dict(self, **kwargs):
        pass


class SecuritiesReportService(XbrlBase):

    def to_dict(self, **kwargs):
        pass

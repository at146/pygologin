from typing import Dict


class ProtocolException(Exception):
    def __init__(self, data: Dict):
        self._json = data
        super().__init__(data.__repr__())

    @property
    def json(self) -> Dict:
        return self._json

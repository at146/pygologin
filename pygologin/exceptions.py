from typing import Any, Dict


class ProtocolException(Exception):
    def __init__(self, data: Dict[str, Any]):
        self._json = data
        super().__init__(data.__repr__())

    @property
    def json(self) -> Dict[str, Any]:
        return self._json

class ProtocolException(Exception):
    def __init__(self, data: dict):
        self._json = data
        super().__init__(data.__repr__())

    @property
    def json(self) -> dict:
        return self._json

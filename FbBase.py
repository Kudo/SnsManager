class FbBase(object):
    class MockLogger(object):
        def __init__(self, *args, **kwargs):
            return None
        def __call__(self, *args, **kwargs):
            return self
        def __getattr__(self, key):
            return self

    def __init__(self, *args, **kwargs):
        """
        Constructor of FbBase

        In:
            accessToken         --  accessToken
            logger              --  logger *optional*

        """
        if 'accessToken' not in kwargs:
            raise ValueError('Invalid parameters.')
        self.accessToken = kwargs['accessToken']
        self.logger = kwargs['logger'] if 'logger' in kwargs else FbBase.MockLogger()

        self.graphUri = 'https://graph.facebook.com/'
        self._timeout = 10

class FbErrorCode(object):
    S_OK=0x00000000

    E_FAILED=0x10000000

    @classmethod
    def IS_SUCCEEDED(cls, errorCode):
        return not cls.IS_FAILED(errorCode)

    @classmethod
    def IS_FAILED(cls, errorCode):
        if (errorCode >> 28) & 1:
            return True
        return False

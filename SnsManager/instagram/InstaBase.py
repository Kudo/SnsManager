from instagram import InstagramAPI, InstagramAPIError, InstagramClientError
from SnsManager.SnsBase import SnsBase
from SnsManager import ErrorCode

class InstaBase(SnsBase):
    def __init__(self, *args, **kwargs):
        super(InstaBase, self).__init__(*args, **kwargs)
        self.myId = self.getMyId()

    def getMyId(self):
        try:
            api = InstagramAPI(access_token=self._accessToken)
            self.myId = api.user().id
        except:
            return None
        return self.myId

    def isTokenValid(self):
        try:
            api = InstagramAPI(access_token=self._accessToken)
            api.user()
        except InstagramAPIError as e:
            return ErrorCode.E_INVALID_TOKEN
        except:
            self._logger.exception('InstaBase::isTokenValid() exception')
            return ErrorCode.E_FAILED
        else:
            return ErrorCode.S_OK

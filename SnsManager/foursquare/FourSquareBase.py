import foursquare
from SnsManager.SnsBase import SnsBase
from SnsManager import ErrorCode

class FourSquareBase(SnsBase):
    def __init__(self, *args, **kwargs):
        super(FourSquareBase, self).__init__(*args, **kwargs)
        self.myId = self.getMyId()

    def getMyId(self):
        user = self.getUserData()
        if user is None:
            return None
        self.myId = user['id']
        return self.myId

    def isTokenValid(self):
        ret = self.getMyId()
        if ret is None:
            return ErrorCode.E_INVALID_TOKEN
        else:
            return ErrorCode.S_OK

    def getUserData(self, user_id='self'):
        try:
            client = foursquare.Foursquare()
            client.set_access_token(self._accessToken)
            ret = client.users(USER_ID=user_id)
            if 'user' not in ret:
                return None
            user = ret['user']
            
            retDict = {
                'name': "{0} {1}".format(user['firstName'] , user['lastName']),
                'id': user['id'],
            }
            if 'photo' in user:
                if isinstance(user['photo'], dict):
                    retDict['avatar'] = "{0}{1}".format(user['photo']['prefix'], user['photo']['suffix'])
                else:
                    retDict['avatar'] = user['photo']
    
            return retDict
        except:
            return None



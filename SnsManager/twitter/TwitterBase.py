import tweepy
from SnsManager.SnsBase import SnsBase
from SnsManager import ErrorCode

class TwitterBase(SnsBase):
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        for k in ['accessTokenSecret', 'consumerKey', 'consumerSecret']:
            if k not in kwargs:
                raise ValueError('Invalid parameters.')
            setattr(self, '_' + k, kwargs[k])
        _auth = tweepy.OAuthHandler(self._consumerKey, self._consumerSecret)
        _auth.set_access_token(self._accessToken, self._accessTokenSecret)
        self._tweepy = tweepy.API(_auth)

        self.myId = self.getMyId()

    def getMyId(self):
        try:
            self.myId = self._tweepy.me().screen_name
        except tweepy.TweepError as e:
            return None
        return self.myId

    def isTokenValid(self):
        try:
            _myId  = self._tweepy.me().name
        except tweepy.TweepError as e:
            return ErrorCode.E_INVALID_TOKEN
        return ErrorCode.S_OK

import copy
import tweepy
from TwitterBase import TwitterBase
from SnsManager import ErrorCode, IExporter

class TwitterExporter(TwitterBase, IExporter):
    _API_LIST = ['user_timeline', 'favorites', 'retweeted_by_me']

    def __init__(self, *args, **kwargs):
        super(TwitterExporter, self).__init__(*args, **kwargs)

        self.verbose = kwargs['verbose'] if 'verbose' in kwargs else False


    def getData(self, **kwargs):
        """
        In:
            lastSyncId *optional*       --  The last synced ID which is a dict type for different API's ID.
            exportDirection             --  self.EXPORT_DIRECTION_FORWARD or self.EXPORT_DIRECTION_BACKWARD

        Out:
            Return a python dict object
            {
                'data': {               # List of data
                    'id': {
                        'message': 'Text',
                        'createdTime': <python datetime>,
                    }, ...
                },
                'count': 30,                    # count in data dic
                'lastSyncId': {'user_timeline': 123, ...},      # last synced id
                'retCode': ErrorCode.S_OK,    # returned code which is instance of ErrorCode

            }
        """
        retDict = {
            'retCode': ErrorCode.E_FAILED,
            'count': 0,
            'lastSyncId': None,
            'data': {},
        }
        lastSyncId = kwargs.get('lastSyncId', None)
        exportDirection = kwargs.get('exportDirection', self.EXPORT_DIRECTION_FORWARD)
        limit = kwargs.get('limit', 300)

        tokenValidRet = self.isTokenValid()
        if ErrorCode.IS_FAILED(tokenValidRet):
            retDict['retCode'] = tokenValidRet
            return retDict

        if not self.myId:
            return retDict

        retLastSyncId = copy.copy(lastSyncId) or {}
        for api in self._API_LIST:
            if api not in retLastSyncId:
                retLastSyncId[api] = None
            if exportDirection == self.EXPORT_DIRECTION_BACKWARD:
                params = {}
                if type(lastSyncId) == dict and api in lastSyncId:
                    params['max_id'] = lastSyncId[api] - 1
                for status in tweepy.Cursor(getattr(self._tweepy, api), **params).items(limit=limit):
                    data = {
                        'id': status.id,
                        'message': status.text,
                        'createdTime': status.created_at,
                        'type': api,
                    }
                    retLastSyncId[api] = status.id
                    retDict['data'][data['id']] = data
            else:
                if type(lastSyncId) == dict and api in lastSyncId:
                    params = {'since_id': lastSyncId[api]}
                    for status in tweepy.Cursor(getattr(self._tweepy, api), **params).items():
                        if not retLastSyncId[api]:
                            retLastSyncId[api] = status.id
                        data = {
                            'id': status.id,
                            'message': status.text,
                            'createdTime': status.created_at,
                            'type': api,
                        }
                        retDict['data'][data['id']] = data
                else:
                    # for FORWARD sync with no lastSyncId case, we would only to retrieve latest item's id.
                    for firstStatus in tweepy.Cursor(getattr(self._tweepy, api)).items(limit=1):
                        retLastSyncId[api] = firstStatus.id

        retDict['lastSyncId'] = retLastSyncId
        retDict['count'] = len(retDict['data'])
        if retDict['count'] == 0:
            retDict['retCode'] = ErrorCode.E_NO_DATA
        else:
            retDict['retCode'] = ErrorCode.S_OK

        return retDict

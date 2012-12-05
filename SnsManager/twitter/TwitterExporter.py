import tweepy
from TwitterBase import TwitterBase
from SnsManager import ErrorCode, IExporter

class TwitterExporter(TwitterBase, IExporter):
    def __init__(self, *args, **kwargs):
        super(TwitterExporter, self).__init__(*args, **kwargs)

        self.verbose = kwargs['verbose'] if 'verbose' in kwargs else False


    def getData(self, **kwargs):
        """
        In:
            lastSyncId *optional*       --  The last synced ID
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
                'retCode': ErrorCode.S_OK,    # returned code which is instance of ErrorCode

            }
        """
        retDict = {
            'retCode': ErrorCode.E_FAILED,
            'count': 0,
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

        retLastSyncId = None
        if exportDirection == self.EXPORT_DIRECTION_BACKWARD:
            params = {}
            if lastSyncId:
                params['max_id'] = lastSyncId - 1
            for status in tweepy.Cursor(self._tweepy.user_timeline, **params).items(limit=limit):
                data = {
                    'id': status.id,
                    'message': status.text,
                    'createdTime': status.created_at
                }
                retLastSyncId = status.id
                retDict['data'][data['id']] = data
        else:
            params = {}
            if lastSyncId:
                params['since_id'] = lastSyncId
            for status in tweepy.Cursor(self._tweepy.user_timeline, **params).items():
                if not retLastSyncId:
                    retLastSyncId = status.id
                data = {
                    'id': status.id,
                    'message': status.text,
                    'createdTime': status.created_at
                }
                retDict['data'][data['id']] = data

        retDict['lastSyncId'] = retLastSyncId
        retDict['count'] = len(retDict['data'])
        retDict['retCode'] = ErrorCode.S_OK

        return retDict

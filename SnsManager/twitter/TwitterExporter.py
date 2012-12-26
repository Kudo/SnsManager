import re
import copy
import tweepy
from TwitterBase import TwitterBase
from SnsManager import ErrorCode, IExporter

class TwitterExporter(TwitterBase, IExporter):
    _API_LIST = ['user_timeline', 'favorites', 'retweeted_by_me']
    _RE_URL = 'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'

    def __init__(self, *args, **kwargs):
        super(TwitterExporter, self).__init__(*args, **kwargs)

        self.verbose = kwargs['verbose'] if 'verbose' in kwargs else False


    def getData(self, **kwargs):
        """
        In:
            lastSyncId *optional*       --  The last synced ID which is a dict type for different API's ID.
            exportDirection             --  self.EXPORT_DIRECTION_FORWARD or self.EXPORT_DIRECTION_BACKWARD
            limit *optional*            --  The record limit to export (only usable of EXPORT_DIRECTION_BACKWARD)

        Out:
            Return a python dict object
            {
                'data': {               # List of data
                    'id': {
                        'message': 'Text',
                        'createdTime': <python datetime>,
                        'links': ['http://www.google.com/', '...']      # Extracted URLs
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
                params = {
                    'include_entities': True,
                }
                if type(lastSyncId) == dict and api in lastSyncId:
                    params['max_id'] = int(lastSyncId[api]) - 1
                for status in tweepy.Cursor(getattr(self._tweepy, api), **params).items(limit=limit):
                    parsedData = self._parseData(api, status)
                    retLastSyncId[api] = str(status.id)
                    retDict['data'][parsedData['id']] = parsedData
            else:
                if type(lastSyncId) == dict and api in lastSyncId:
                    retLastSyncId[api] = None
                    params = {
                        'include_entities': True,
                        'since_id': int(lastSyncId[api]),
                    }
                    itemParams = {}
                else:
                    # for FORWARD sync with no lastSyncId case, we would only to retrieve latest item's id.
                    params = {'include_entities': True}
                    itemParams = {'limit' : 1}

                for status in tweepy.Cursor(getattr(self._tweepy, api), **params).items(**itemParams):
                    if not retLastSyncId[api]:
                        retLastSyncId[api] = str(status.id)
                    parsedData = self._parseData(api, status)
                    retDict['data'][parsedData['id']] = parsedData

                if not retLastSyncId[api]:
                    del retLastSyncId[api]

        retDict['lastSyncId'] = retLastSyncId if retLastSyncId else None
        retDict['count'] = len(retDict['data'])
        if retDict['count'] == 0:
            retDict['retCode'] = ErrorCode.E_NO_DATA
        else:
            retDict['retCode'] = ErrorCode.S_OK

        return retDict

    def _parseData(self, apiName, status):
        data = {
            'id': str(status.id),
            'message': status.text,
            'createdTime': status.created_at,
            'type': apiName,
            'links': self._extractUrls(status),
        }
        return data

    def _extractUrls(self, status):
        links = []

        # [0] Extract URLs from text
        linksInText = re.findall(self._RE_URL, status.text)

        # [1] Get extracted URLs by Twitter
        linksToExclude = []
        for url in status.entities['urls']:
            links.append(url['expanded_url'])
            linksToExclude.append(url['url'])

        # [2] Exclude URLs from text duplicated in Twitter extracted (a.k.a. http://t.co/.... )
        linksInText = [url for url in linksInText if url not in linksToExclude]

        # [3] Merge two sets of URLs
        links += linksInText

        return links

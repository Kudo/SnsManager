import copy
import libgreader
from datetime import datetime
from GoogleBase import GoogleBase
from SnsManager import ErrorCode, IExporter

class GoogleReaderExporter(GoogleBase, IExporter):
    def __init__(self, *args, **kwargs):
        super(GoogleReaderExporter, self).__init__(*args, **kwargs)

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

        auth = libgreader.auth.GAPDecoratorAuthMethod(self.credentials)
        gReader = libgreader.GoogleReader(auth)
        gReaderContainer = libgreader.SpecialFeed(gReader, libgreader.ReaderUrl.STARRED_LIST)

        retLastSyncId = copy.copy(lastSyncId) or {}
        service = 'reader'
        if service not in retLastSyncId:
            retLastSyncId[service] = None

        if exportDirection == self.EXPORT_DIRECTION_BACKWARD:
            params = {
                'loadLimit': limit,
            }
            if type(lastSyncId) == dict and service in lastSyncId:
                params['until'] = lastSyncId[service] - 1

            gReaderContainer.loadItems(**params)
            for item in gReaderContainer.items:
                parsedData = self._parseData(item)
                retLastSyncId[service] = item.time
                retDict['data'][parsedData['id']] = parsedData
        else:
            if type(lastSyncId) == dict and service in lastSyncId:
                params = {
                    'loadLimit': limit,
                    'since': lastSyncId[service] + 1,
                }
            else:
                # for FORWARD sync with no lastSyncId case, we would only to retrieve latest item's id.
                params = {'loadLimit': 1}

            gReaderContainer.loadItems(**params)
            retLastSyncId[service] = None
            for item in gReaderContainer.items:
                if not retLastSyncId[service]:
                    retLastSyncId[service] = item.time
                parsedData = self._parseData(item)
                retDict['data'][parsedData['id']] = parsedData

        retDict['lastSyncId'] = retLastSyncId
        retDict['count'] = len(retDict['data'])
        if retDict['count'] == 0:
            retDict['retCode'] = ErrorCode.E_NO_DATA
        else:
            retDict['retCode'] = ErrorCode.S_OK

        return retDict

    def _parseData(self, item):
        data = {
            'id': item.time,
            'createdTime': datetime.fromtimestamp(item.time),
            'links': [item.url],
        }
        return data

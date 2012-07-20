import os
import time
import uuid
import dateutil
import urllib2
from datetime import datetime
from dateutil import parser as dateParser
from instagram import InstagramAPI, InstagramAPIError, InstagramClientError
from InstaBase import InstaBase
from SnsManager import ErrorCode, IExporter

class InstaExporter(InstaBase, IExporter):
    def __init__(self, *args, **kwargs):
        """
        Constructor of FbExporter

        In:
            tmpFolder           --  tmp folder to store photo files *optional* default is /tmp 

        """
        super(InstaExporter, self).__init__(*args, **kwargs)

        self._tmpFolder = kwargs['tmpFolder'] if 'tmpFolder' in kwargs else '/tmp'
        self.verbose = kwargs['verbose'] if 'verbose' in kwargs else False

    def getData(self, since=None, until=None):
        """
        Get data from Instagram feed

        In:
            since           --  The start time to get data
                                given None means current time
                                or given python's datetime instance as input
            until           --  The end time to get date
                                given None means yesterday
                                or given python's datetime instance as input

            Example: (Please note that the direction to retrieve data is backward)
                Now   --->   2012/04/01   --->   2012/01/01
                You can specify since=None and until=<datetime of 2012/01/01>
                or since=<datetime of 2012/04/01> until=<datetime of 2012/01/01>

        Out:
            Return a python dict object
            {
                'data': {               # List of data
                    'id': {
                        'id': 'postId',
                        'message': 'Text',
                        'photos': [ '/path/to/file' ],
                        'createdTime': <datetime object>,
                        'place': {      # *optional*
                            'id': 'locationId',
                            'name': 'locationName',
                            'latitude': nnn.nnn,
                            'longitude' mmm.mmm
                        }
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

        if not until:
            until = datetime.now() - timedelta(1)

        tokenValidRet = self.isTokenValid()
        if ErrorCode.IS_FAILED(tokenValidRet):
            retDict['retCode'] = tokenValidRet
            return retDict

        if not self.myId:
            return retDict

        sinceTimestamp = self._datetime2Timestamp(since) + 1 if since else None
        untilTimestamp = self._datetime2Timestamp(until) - 1 if until else None
        api = InstagramAPI(access_token=self._accessToken)
        for media in api.user_recent_media(max_pages=999, min_timestamp=untilTimestamp, max_timestamp=sinceTimestamp):
            if not media:
                break
            for data in media:
                data = self._transformFormat(data)
                self._dumpData(data)
                retDict['data'][data['id']] = data

        retDict['count'] = len(retDict['data'])
        retDict['retCode'] = ErrorCode.S_OK
        return retDict

    def _datetime2Timestamp(self, datetimeObj):
        return int(time.mktime(datetimeObj.timetuple()))

    def _transformFormat(self, data):
        retData = {
            'id': data.id,
            'message': data.caption.text,
            'createdTime': data.created_time,
            'photos': []
        }

        if hasattr(data, 'location'):
            retData['place'] = data.location
        fPath = self._storeFileToTemp(data.images['standard_resolution'].url)
        if fPath:
            retData['photos'].append(fPath)
        return retData

    def _storeFileToTemp(self, fileUri):
        fileExtName = fileUri[fileUri.rfind('.') + 1:]
        newFileName = os.path.join(self._tmpFolder, "{0}.{1}".format(str(uuid.uuid1()), fileExtName))
        try:
            conn = urllib2.urlopen(fileUri)
            fileObj = file(newFileName, 'w')
            fileObj.write(conn.read())
            fileObj.close()
        except:
            return None
        return newFileName

    def _dumpData(self, data):
        if self.verbose:
            output = u"\n"
            for k, v in data.iteritems():
                val = v
                if isinstance(val, datetime):
                    val = val.isoformat()
                output += u"%s[%s]\n" % (k, val)
            self._logger.debug(output.encode('utf-8'))

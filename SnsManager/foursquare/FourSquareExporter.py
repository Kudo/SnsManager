import os
import time
import uuid
import dateutil
import urllib2
import foursquare
from datetime import datetime
from dateutil import parser as dateParser
from FourSquareBase import FourSquareBase
from SnsManager import ErrorCode, IExporter

class FourSquareExporter(FourSquareBase, IExporter):
    def __init__(self, *args, **kwargs):
        """
        Constructor of FbExporter
        """
        super(FourSquareExporter, self).__init__(*args, **kwargs)

        self.verbose = kwargs['verbose'] if 'verbose' in kwargs else False


    def getData(self, **kwargs):
        """
        Get data from foursquare /users/checkins

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
            'data': [],
        }
        since = kwargs.get('since', None)
        until = kwargs.get('until', None)

        if not until:
            until = datetime.now() - timedelta(10)

        fqLaunchDate = datetime(2009, 3, 11, 12, 0, 0)
        if since < fqLaunchDate:
            retDict['retCode'] = ErrorCode.E_NO_DATA
            return retDict

        tokenValidRet = self.isTokenValid()
        if ErrorCode.IS_FAILED(tokenValidRet):
            retDict['retCode'] = tokenValidRet
            return retDict

        if not self.myId:
            return retDict

        sinceTimestamp = self._datetime2Timestamp(since) + 1 if since else None
        untilTimestamp = self._datetime2Timestamp(until) - 1 if until else None
        client = foursquare.Foursquare()
        client.set_access_token(self._accessToken) 

        ret = client.users.checkins(params={'sort':'newestfirst', 'afterTimestamp':untilTimestamp, 'beforeTimestamp':sinceTimestamp})
        if 'checkins' not in ret:
            return retDict
        checkins = ret['checkins']
        for item in checkins['items']:
            if not item:
                break
            if 'venue' not in item:
                continue
            shout = item['shout'] if 'shout' in item else None
            venue = item['venue']
            place = { 'name': venue['name'] }
            if 'location' in venue:
                place['latitude'] = venue['location']['lat'] 
                place['longitude'] = venue['location']['lng'] 

            people = []
            if 'entities' in item:
                for entity in item['entities']:
                    if entity['type'] != 'user':
                        continue
                    person = self.getUserData(user_id=entity['id'])
                    people.append(person)
            retDict['data'].append({
                    'message': shout,
                    'place': place,
                    'people': people
            })
        retDict['count'] = len(retDict['data'])
        retDict['retCode'] = ErrorCode.S_OK

        return retDict       
                    
        
    def _datetime2Timestamp(self, datetimeObj):
        return int(time.mktime(datetimeObj.timetuple()))



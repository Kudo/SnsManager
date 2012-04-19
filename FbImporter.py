import urllib, urllib2
import json
import dateutil
from datetime import datetime
from FbBase import FbBase, FbErrorCode

class FbImporter(FbBase):
    class DIRECTION:
        FORWARD=1,
        BACKWARD=2

    def __init__(self, *args, **kwargs):
        """
        Constructor of FbBase

        In:
            tmpFolder           --  tmp folder to store photo files *optional* default is /tmp 

        """
        FbBase.__init__(self, *args, **kwargs)

        self._tmpFolder = kwargs['tmpFolder'] if 'tmpFolder' in kwargs else '/tmp'

    def getData(self, direction=DIRECTION.FORWARD, since=None, limits=30):
        """
        Get data from Facebook feed

        In:
            direction       --  Direction to retrieve data
            since           --  The start time to get data
                                given None means current time
                                or given python's datetime instance as input
            limits          --  Entities number to retrieve


        Out:
            Return a python dict object
            {
                'data': [               # List of data
                    {
                        'message': 'Text',
                        'links': [ 'uri' ],
                        'attachments': [ 'localPathToAttachment' ],
                    },
                ],
                'count': 30,            # count in data list
                'retCode': FbErrorCode.S_OK, # returned code which is instance of FbErrorCode
                'retDesciption: "OK",   # Non-localized of returned description
            }
        """
        return None

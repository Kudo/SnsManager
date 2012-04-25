Facebook Importer
====================

1. Introduction
---------------------
An python module to retrieve Facebook's data based on Graph API.

2. Installation
---------------------
- clone to some where and use locally


3. Usage
---------------------
- To retrieve personal information

```python
from FbUserInfo import FbUserInfo

fbObj = FbUserInfo(accessToken=<AccessToken>)
fbObj.getMyName()		    # Get name
fbObj.getMyEmail()		    # Get email
fbObj.getMyAvatar()		    # Get avatar uri
```

- To get feed data

```python
from FbBase import FbErrorCode
from FbImporter import FbImporter

fbObj = FbImporter(accessToken=<AccessToken>)
retDict = fbObj.getData()
if FbErrorCode.IS_SUCCEEDED(retDict['retCode']):
    for data in retDict['data']:
	...
    count = retDict['count']
else:
    print retDict['retCode']
```


#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, os.path
import datetime
# Hack for import module in grandparent folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
import unittest
from SnsManager import ErrorCode
from SnsManager.foursquare import FourSquareBase, FourSquareExporter

TEST_TOKEN = '0KEU2ABNO4Y31NXORDIRUFTMJKADS4RMWELMN2QMDN0UWZEO'

class TestFourSquareBase(unittest.TestCase):
    def test_GetMyId_GivenValidToken_True(self):
        obj = FourSquareBase(accessToken=TEST_TOKEN)
        self.assertTrue(obj.getMyId())

    def test_GetMyId_GivenInvalidToken_None(self):
        obj = FourSquareBase(accessToken='invalid_token')
        self.assertIsNone(obj.getMyId())

    def test_IsTokenValid_GivenValidToken_S_OK(self):
        obj = FourSquareBase(accessToken=TEST_TOKEN)
        resp = obj.isTokenValid()
        self.assertEqual(resp, ErrorCode.S_OK)

    def test_IsTokenValid_GivenInValidToken_E_INVALID_TOKEN(self):
        obj = FourSquareBase(accessToken='invalid_token')
        resp = obj.isTokenValid()
        self.assertEqual(resp, ErrorCode.E_INVALID_TOKEN)

    def test_getData_MULTIPLE_DATA(self):
        obj = FourSquareExporter(accessToken=TEST_TOKEN)
        currDatetime = datetime.datetime.now()
        tendayBefore = currDatetime - datetime.timedelta(10)
        ret = obj.getData(since=currDatetime, until=tendayBefore)
        self.assertIsNotNone(ret)
        self.assertTrue(ret['count'] > 0)
        self.assertTrue(len(ret['data']) > 0)
        self.assertEqual(ret['retCode'], ErrorCode.S_OK)

    def test_getData_E_NO_DATA(self):
        obj = FourSquareExporter(accessToken=TEST_TOKEN)
        currDatetime = datetime.datetime(2008, 11, 11)
        tendayBefore = currDatetime - datetime.timedelta(1)
        ret = obj.getData(since=currDatetime, until=tendayBefore)
        self.assertEqual(ret['retCode'], ErrorCode.E_NO_DATA)
 
if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFourSquareBase)
    unittest.TextTestRunner(verbosity=2).run(suite)

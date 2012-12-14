#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, os.path
# Hack for import module in grandparent folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
import unittest
from SnsManager import ErrorCode
from SnsManager.google import GoogleBase

TEST_TOKEN = 'TEST_TOKEN'
REFRESH_TOKEN = '1/RFbvYbBG4DQaV6oiJ-qOYV9z7vnpFfWuZFxA9Smlymw'
CLIENT_ID = '428554203189.apps.googleusercontent.com'
CLIENT_SECRET = 'UCH9e0zHNrmw6U7TEmm7W-0Y'

class TestGoogleBase(unittest.TestCase):
    def test_GetMyId_GivenValidToken_True(self):
        obj = GoogleBase(accessToken=TEST_TOKEN, refreshToken=REFRESH_TOKEN, clientId=CLIENT_ID, clientSecret=CLIENT_SECRET)
        self.assertTrue(obj.getMyId())

    def test_GetMyId_GivenInvalidToken_None(self):
        obj = GoogleBase(accessToken='invalid token', refreshToken='invalid token', clientId=CLIENT_ID, clientSecret=CLIENT_SECRET)
        self.assertIsNone(obj.getMyId())

    def test_IsTokenValid_GivenValidToken_S_OK(self):
        obj = GoogleBase(accessToken=TEST_TOKEN, refreshToken=REFRESH_TOKEN, clientId=CLIENT_ID, clientSecret=CLIENT_SECRET)
        resp = obj.isTokenValid()
        self.assertEqual(resp, ErrorCode.S_OK)

    def test_IsTokenValid_GivenInValidToken_E_INVALID_TOKEN(self):
        obj = GoogleBase(accessToken='invalid token', refreshToken='invalid token', clientId=CLIENT_ID, clientSecret=CLIENT_SECRET)
        resp = obj.isTokenValid()
        self.assertEqual(resp, ErrorCode.E_INVALID_TOKEN)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestGoogleBase)
    unittest.TextTestRunner(verbosity=2).run(suite)

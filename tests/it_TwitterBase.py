#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, os.path
# Hack for import module in grandparent folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
import unittest
from SnsManager import ErrorCode
from SnsManager.twitter import TwitterBase

CONSUMER_KEY = 'ZglRcsve5lAp5h12nJ4APA'
CONSUMER_SECRET = 'zBch3rtBh9AmaHY4EitodNdbKVgsuiqzB4dWzDvG3RQ'
TEST_TOKEN = 'TEST_TOKEN'
TEST_TOKEN_SECRET = 'TEST_TOKEN_SECRET'

class TestTwitterBase(unittest.TestCase):
    def test_GetMyId_GivenValidToken_True(self):
        obj = TwitterBase(accessToken=TEST_TOKEN, accessTokenSecret=TEST_TOKEN_SECRET, consumerKey=CONSUMER_KEY, consumerSecret=CONSUMER_SECRET)
        self.assertTrue(obj.getMyId())

    def test_GetMyId_GivenInvalidToken_None(self):
        obj = TwitterBase(accessToken='invalid_token', accessTokenSecret=TEST_TOKEN_SECRET, consumerKey=CONSUMER_KEY, consumerSecret=CONSUMER_SECRET)
        self.assertIsNone(obj.getMyId())

    def test_IsTokenValid_GivenValidToken_S_OK(self):
        obj = TwitterBase(accessToken=TEST_TOKEN, accessTokenSecret=TEST_TOKEN_SECRET, consumerKey=CONSUMER_KEY, consumerSecret=CONSUMER_SECRET)
        resp = obj.isTokenValid()
        self.assertEqual(resp, ErrorCode.S_OK)

    def test_IsTokenValid_GivenInValidToken_E_INVALID_TOKEN(self):
        obj = TwitterBase(accessToken='invalid_token', accessTokenSecret=TEST_TOKEN_SECRET, consumerKey=CONSUMER_KEY, consumerSecret=CONSUMER_SECRET)
        resp = obj.isTokenValid()
        self.assertEqual(resp, ErrorCode.E_INVALID_TOKEN)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTwitterBase)
    unittest.TextTestRunner(verbosity=2).run(suite)

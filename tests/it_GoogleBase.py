#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, os.path
# Hack for import module in grandparent folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
import unittest
from SnsManager import ErrorCode
from SnsManager.google import GoogleBase

TEST_TOKEN = 'ya29.AHES6ZSOEi2x7tbciVT2VNRTofIBfxnXapO01WtHf5HzIw'

class TestGoogleBase(unittest.TestCase):
    def test_GetMyId_GivenValidToken_True(self):
        obj = GoogleBase(accessToken=TEST_TOKEN)
        self.assertTrue(obj.getMyId())

    def test_GetMyId_GivenInvalidToken_None(self):
        obj = GoogleBase(accessToken='invalid_token')
        self.assertIsNone(obj.getMyId())

    def test_IsTokenValid_GivenValidToken_S_OK(self):
        obj = GoogleBase(accessToken=TEST_TOKEN)
        resp = obj.isTokenValid()
        self.assertEqual(resp, ErrorCode.S_OK)

    def test_IsTokenValid_GivenInValidToken_E_INVALID_TOKEN(self):
        obj = GoogleBase(accessToken='invalid_token')
        resp = obj.isTokenValid()
        self.assertEqual(resp, ErrorCode.E_INVALID_TOKEN)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestGoogleBase)
    unittest.TextTestRunner(verbosity=2).run(suite)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, os.path
# Hack for import module in grandparent folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
sys.path.append('/Users/kudo/01_Work/Repos/python-instagram')
import unittest
from SnsManager import ErrorCode
from SnsManager.instagram import InstaBase

TEST_TOKEN = '31413082.8d5ac3f.ad80209831e34da0b894e784f8536394'

class TestInstaBase(unittest.TestCase):
    def test_GetMyId_GivenValidToken_True(self):
        obj = InstaBase(accessToken=TEST_TOKEN)
        self.assertTrue(obj.getMyId())

    def test_GetMyId_GivenInvalidToken_None(self):
        obj = InstaBase(accessToken='invalid_token')
        self.assertIsNone(obj.getMyId())

    def test_IsTokenValid_GivenValidToken_S_OK(self):
        obj = InstaBase(accessToken=TEST_TOKEN)
        resp = obj.isTokenValid()
        self.assertEqual(resp, ErrorCode.S_OK)

    def test_IsTokenValid_GivenInValidToken_E_INVALID_TOKEN(self):
        obj = InstaBase(accessToken='invalid_token')
        resp = obj.isTokenValid()
        self.assertEqual(resp, ErrorCode.E_INVALID_TOKEN)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestInstaBase)
    unittest.TextTestRunner(verbosity=2).run(suite)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    test_FbBase.py - Integration test for FbBase
"""
import sys, os.path
# Hack for import module in grandparent folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
import unittest
from SnsManager.facebook.FbBase import FbBase

TEST_TOKEN = 'AccessToken'

class TestFbBase(unittest.TestCase):
    def test_GetMyName_EqualMyName_True(self):
        obj = FbBase(accessToken=TEST_TOKEN)
        self.assertEqual(obj.getMyName(), 'Kudo Chien')

    def test_GetMyEmail_EqualMyEmail_True(self):
        obj = FbBase(accessToken=TEST_TOKEN)
        self.assertEqual(obj.getMyEmail(), 'ckchien@gmail.com')

    def test_GetMyAvatar_HasAvatarUri_True(self):
        obj = FbBase(accessToken=TEST_TOKEN)
        self.assertTrue(obj.getMyAvatar())

    def test_IsTokenValid_GivenValidToken_True(self):
        obj = FbBase(accessToken=TEST_TOKEN)
        self.assertTrue(obj.isTokenValid())

    def test_IsTokenValid_GivenInValidToken_False(self):
        obj = FbBase(accessToken='invalid_token')
        self.assertFalse(obj.isTokenValid())


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFbBase)
    unittest.TextTestRunner(verbosity=2).run(suite)

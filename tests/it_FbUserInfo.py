#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    test_FbUserInfo.py - Integration test for FbUserInfo
"""
import sys, os.path
# Hack for import module in grandparent folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
from FbUserInfo import FbUserInfo
import unittest

TEST_TOKEN = 'AccessToken'

class TestFbUserInfo(unittest.TestCase):
    def test_GetMyName_EqualMyName(self):
        obj = FbUserInfo(accessToken=TEST_TOKEN)
        self.assertEqual(obj.getMyName(), 'John Doe')

    def test_GetMyEmail_EqualMyEmail(self):
        obj = FbUserInfo(accessToken=TEST_TOKEN)
        self.assertEqual(obj.getMyEmail(), 'john.doe@gmail.com')

    def test_GetMyAvatar_HasAvatarUri(self):
        obj = FbUserInfo(accessToken=TEST_TOKEN)
        self.assertTrue(obj.getMyAvatar())

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFbUserInfo)
    unittest.TextTestRunner(verbosity=2).run(suite)

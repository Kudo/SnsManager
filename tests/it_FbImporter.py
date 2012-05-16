#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    test_FbImporter.py - Integration test for FbImporter
"""
import sys, os.path
# Hack for import module in grandparent folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
from FbBase import FbErrorCode
from FbImporter import FbImporter
import unittest
import logging

TEST_TOKEN = 'AccessToken'

class TestFbImporter(unittest.TestCase):
    def test_GetData_ReturnValidFormat_True(self):
        obj = FbImporter(accessToken=TEST_TOKEN)
        resp = obj.getData()
        self.assertIn('retCode', resp)
        self.assertEqual(resp['retCode'], FbErrorCode.S_OK)
        self.assertTrue(FbErrorCode.IS_SUCCEEDED(resp['retCode']))
        self.assertIn('data', resp)
        self.assertTrue(type(resp['data']), list)
        self.assertIn('count', resp)
        self.assertTrue(type(resp['count']), int)

    def test_GetData_GivenInvalidToken_ReturnInvalidToken(self):
        obj = FbImporter(accessToken=TEST_TOKEN)
        resp = obj.getData()
        self.assertIn('retCode', resp)
        self.assertEqual(resp['retCode'], FbErrorCode.E_INVALID_TOKEN)

    def test_IsTokenValid_GivenValidToken_True(self):
        obj = FbImporter(accessToken=TEST_TOKEN)
        self.assertTrue(obj.isTokenValid())

    def test_IsTokenValid_GivenInValidToken_False(self):
        obj = FbImporter(accessToken='invalid_token')
        self.assertFalse(obj.isTokenValid())

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFbImporter)
    unittest.TextTestRunner(verbosity=2).run(suite)

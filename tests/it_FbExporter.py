#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    test_FbExporter.py - Integration test for FbExporter
"""
import sys, os.path
# Hack for import module in grandparent folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
from SnsManager import ErrorCode
from SnsManager.facebook.FbExporter import FbExporter
import unittest
import logging

TEST_TOKEN = 'TestToken'

class TestFbExporter(unittest.TestCase):
    def test_GetData_ReturnValidFormat_True(self):
        obj = FbExporter(accessToken=TEST_TOKEN)
        resp = obj.getData()
        self.assertIn('retCode', resp)
        self.assertEqual(resp['retCode'], ErrorCode.S_OK)
        self.assertTrue(ErrorCode.IS_SUCCEEDED(resp['retCode']))
        self.assertIn('data', resp)
        self.assertTrue(type(resp['data']), list)
        self.assertIn('count', resp)
        self.assertTrue(type(resp['count']), int)

    def test_GetData_GivenInvalidToken_ReturnInvalidToken(self):
        obj = FbExporter(accessToken='invalid_token')
        resp = obj.getData()
        self.assertIn('retCode', resp)
        self.assertEqual(resp['retCode'], ErrorCode.E_INVALID_TOKEN)

    def test_IsTokenValid_GivenValidToken_S_OK(self):
        obj = FbExporter(accessToken=TEST_TOKEN)
        resp = obj.isTokenValid()
        self.assertEqual(resp, ErrorCode.S_OK)

    def test_IsTokenValid_GivenInValidToken_E_INVALID_TOKEN(self):
        obj = FbExporter(accessToken='invalid_token')
        resp = obj.isTokenValid()
        self.assertEqual(resp, ErrorCode.E_INVALID_TOKEN)

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFbExporter)
    unittest.TextTestRunner(verbosity=2).run(suite)

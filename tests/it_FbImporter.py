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

TEST_TOKEN = 'AccessToken'

class TestFbImporter(unittest.TestCase):
    def test_GetData_ReturnValidFormat(self):
        obj = FbImporter(accessToken=TEST_TOKEN)
        resp = obj.getData()
        self.assertIn('retCode', resp)
        self.assertIsInstance(resp['retCode'], FbErrorCode)
        self.assertIn('retDesc', resp)
        self.assertIn('data', resp)
        self.assertTrue(type(resp['data']), list)
        self.assertIn('count', resp)
        self.assertTrue(type(resp['count']), int)
        self.assertTrue(obj.getData())

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFbImporter)
    unittest.TextTestRunner(verbosity=2).run(suite)

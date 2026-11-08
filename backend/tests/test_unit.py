import unittest
from unittest.mock import patch
from pydantic import ValidationError
from backend.models import Submission,ProfileInput,MessageInput,distance_miles
from backend.core import signed,verify_signature,demo_enabled

PROFILE={'name':'Test Neighbor','zip':'11372','occupation':'Designer','languages':[' English ','english','Bengali'],'expertise':['career advice']}

class ValidationTests(unittest.TestCase):
    def test_normalization(self):
        p=ProfileInput(**PROFILE)
        self.assertEqual(p.languages,['english','bengali'])
        self.assertEqual(p.cultures,[])

    def test_bad_fields_and_missing_consent(self):
        for change in [{'zip':'123'},{'languages':[]},{'expertise':[]},{'name':'x'},{'cultures':['x'*61]},{'bio':'x'*801}]:
            with self.assertRaises(ValidationError): ProfileInput(**{**PROFILE,**change})
        with self.assertRaises(ValidationError):
            Submission(version=1,formId='test',responseId='1',email='a@example.com',consent=False,adult=True,profile=PROFILE)

    def test_messages(self):
        self.assertEqual(MessageInput(body=' Hello ').body,'Hello')
        for value in ['   ','x'*2001]:
            with self.assertRaises(ValidationError): MessageInput(body=value)

    def test_distance(self):
        self.assertEqual(distance_miles(40.7,-73.9,40.7,-73.9),0)
        self.assertAlmostEqual(distance_miles(40.7,-73.9,40.8,-73.9),6.91,places=2)

    def test_webhook_signatures_and_replays(self):
        body=b'{"version":1}'; stamp='1800000000000'; secret='s'*40
        signature=signed(body,stamp,secret)
        self.assertTrue(verify_signature(body,stamp,signature,secret,1800000000000))
        self.assertFalse(verify_signature(body+b' ',stamp,signature,secret,1800000000000))
        self.assertFalse(verify_signature(body,stamp,signature,secret,1800000300001))
        self.assertFalse(verify_signature(body,stamp,signature,'short',1800000000000))

    def test_production_demo_disabled(self):
        with patch('backend.core.PRODUCTION',True),patch.dict('os.environ',{'DEMO_MODE':'true'}):
            self.assertFalse(demo_enabled())

if __name__=='__main__': unittest.main()

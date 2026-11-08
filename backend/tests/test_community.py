import unittest
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError
from backend.community import PostInput, matches

class CommunityValidationTests(unittest.TestCase):
    def test_targeting_interests_and_profession(self):
        viewer={'interests':['gardening'],'expertise':[],'needs':[],'occupation':'Realtor'}
        self.assertEqual(matches(['gardening','realtor','programming'],viewer),['gardening','realtor'])

    def test_event_validation_and_normalization(self):
        data={'kind':'event','title':'Block party','body':'Come meet your neighbors.', 'zip':'11372',
              'tags':[' Gardening ','gardening'],'venue':'Public park',
              'starts_at':datetime.now(timezone.utc)+timedelta(days=1)}
        self.assertEqual(PostInput(**data).tags,['gardening'])
        for change in ({'starts_at':None},{'venue':' '},{'starts_at':datetime.now(timezone.utc)-timedelta(days=1)}, {'tags':[' ']}):
            with self.assertRaises(ValidationError): PostInput(**{**data,**change})
        with self.assertRaises(ValidationError): PostInput(**{**data,'kind':'need'})

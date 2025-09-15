from ninja.testing import TestAsyncClient
from apps.api import api

aclient = TestAsyncClient(api, headers={"content_type": "application/json"})

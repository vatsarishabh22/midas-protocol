import unittest
from unittest.mock import MagicMock
import time

from backend.application import ProviderManager, ProviderStatus, ProviderDownError

class TestCircuitBreaker(unittest.TestCase):
    def setUp(self):
        self.manager = ProviderManager()

    def test_provider_marked_down_on_failure(self):
        provider_name = "groq"
        mock_provider = MagicMock()
        mock_provider.get_response.side_effect = ProviderDownError("Boom!")
        try:
            mock_provider.get_response() 
        except ProviderDownError:
            self.manager.update_status(provider_name, ProviderStatus.DOWN)

        # 3. ASSERT: Did the manager do its job?
        assert self.manager.providers[provider_name].status == ProviderStatus.DOWN

        # 4. ASSERT:  Check if the difference is less than 1 second
        assert abs(self.manager.providers[provider_name].reset_time - (time.time() + 60)) < 1.0

        # 5. ASSERT: Did the provider get called?
        mock_provider.get_response.assert_called_once()

    def test_provider_recovers_after_timeout(self):
        provider_name = "groq"
        self.manager.providers[provider_name].status = ProviderStatus.DOWN
        self.manager.providers[provider_name].reset_time = time.time()-1

        self.manager.get_provider()

        # ASSERT: Did the manager recovers from its down state to active after timeout ?
        assert self.manager.providers[provider_name].status == ProviderStatus.ACTIVE
        



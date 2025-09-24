import pytest
from unittest.mock import patch, Mock
import os
from zenodo_jupyterlab.server.testConnection import checkZenodoConnection

@pytest.mark.asyncio
async def test_zenodo_connection_success():
    """Success path should return 200 when ZenodoAPI.query_user_deposits reports 200.
    We mock ZenodoAPI to avoid network dependency and real token usage."""
    with patch('zenodo_jupyterlab.server.testConnection.ZenodoAPI') as MockZenAPI:
        mock_instance = MockZenAPI.return_value
        mock_response = Mock(status_code=200)
        mock_instance.query_user_deposits.return_value = mock_response

        with patch.dict(os.environ, {'ZENODO_API_KEY': 'dummy_token', 'ZENODO_SANDBOX': 'true'}):
            status_code, zAPI = await checkZenodoConnection()

        assert status_code == 200
        # Returned zAPI should be the mocked instance
        assert zAPI is mock_instance
        # Ensure query was invoked
        mock_instance.query_user_deposits.assert_called_once()

@pytest.mark.asyncio
async def test_zenodo_connection_failure():
    """Failure path: simulate missing token leading to exception and (0, None)."""
    # Remove token from env to trigger exception access_token lookup
    with patch.dict(os.environ, {}, clear=True):
        status_code, zAPI = await checkZenodoConnection()
    assert status_code == 0
    assert zAPI is None
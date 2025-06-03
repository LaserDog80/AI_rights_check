import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add src directory to Python path to import main
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from main import fetch_license_info, describe_license, LicenseInfo

class TestMain(unittest.TestCase):
    def test_describe_license_common(self):
        self.assertIn("permissive free software license", describe_license("MIT", "API desc"))
        self.assertIn("Apache Software Foundation", describe_license("Apache-2.0", "API desc"))
        self.assertIn("strong copyleft license", describe_license("GPL-3.0", "API desc"))

    def test_describe_license_uncommon(self):
        self.assertEqual("Custom description from API.", describe_license("AGPL-3.0", "Custom description from API."))
        self.assertEqual("Another custom description.", describe_license("LGPL-2.1", "Another custom description."))

    @patch('requests.get')
    def test_fetch_license_info_success(self, mock_get):
        # Simulate successful API response for repo license
        mock_repo_response = MagicMock()
        mock_repo_response.status_code = 200
        mock_repo_response.json.return_value = {
            "license": {
                "key": "mit",
                "name": "MIT License",
                "spdx_id": "MIT",
                "url": "https://api.github.com/licenses/mit",
                "node_id": "MDc6TGljZW5zZTEz"
            }
        }

        # Simulate successful API response for license details
        mock_license_details_response = MagicMock()
        mock_license_details_response.status_code = 200
        mock_license_details_response.json.return_value = {
            "key": "mit",
            "name": "MIT License",
            "spdx_id": "MIT",
            "description": "A short and simple permissive license with conditions only requiring preservation of copyright and license notices."
        }

        # Configure mock_get to return different responses based on URL
        def side_effect(url):
            if "api.github.com/repos" in url:
                return mock_repo_response
            elif "api.github.com/licenses" in url:
                return mock_license_details_response
            return MagicMock(status_code=404) # Default fallback

        mock_get.side_effect = side_effect

        # Test with 'owner/repo'
        license_info = fetch_license_info("owner/repo")
        self.assertIsInstance(license_info, LicenseInfo)
        self.assertEqual(license_info.spdx_id, "MIT")
        self.assertEqual(license_info.name, "MIT License")
        self.assertIn("permissive license", license_info.description)

        # Test with 'https://github.com/owner/repo'
        license_info_url = fetch_license_info("https://github.com/owner/repo")
        self.assertIsInstance(license_info_url, LicenseInfo)
        self.assertEqual(license_info_url.spdx_id, "MIT")

    @patch('requests.get')
    def test_fetch_license_info_no_license(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"license": None} # No license key
        mock_get.return_value = mock_response

        license_info = fetch_license_info("owner/repo-no-license")
        self.assertIsNone(license_info)

    @patch('requests.get')
    def test_fetch_license_info_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        # Import requests.exceptions here or at the top of the file if not already there
        import requests
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("HTTPError 404")
        mock_get.return_value = mock_response

        license_info = fetch_license_info("owner/non-existent-repo")
        self.assertIsNone(license_info)

    @patch('requests.get')
    def test_fetch_license_info_rate_limit(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 403
        # Import requests.exceptions here or at the top of the file if not already there
        import requests
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("HTTPError 403")
        mock_get.return_value = mock_response

        license_info = fetch_license_info("owner/repo")
        self.assertIsNone(license_info)

    def test_fetch_license_info_invalid_url(self):
        license_info = fetch_license_info("invalid-url")
        self.assertIsNone(license_info) # Expect None for invalid format

        license_info_slash = fetch_license_info("invalid/url/format") # too many slashes
        self.assertIsNone(license_info_slash)


    @patch('requests.get')
    def test_fetch_license_info_malformed_json(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Malformed JSON") # Simulate JSON parsing error
        mock_get.return_value = mock_response

        license_info = fetch_license_info("owner/repo-malformed-json")
        self.assertIsNone(license_info)


if __name__ == '__main__':
    unittest.main()

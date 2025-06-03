"""Skeleton module for fetching GitHub license information.

This template provides placeholders for implementing a simple command-line
application. The final code should:
    1. Parse a GitHub repository URL or "owner/repo" string from the command
       line.
    2. Query the GitHub REST API to obtain the repository's license details.
    3. Print the license name along with a short description of what the license
       allows.

You can extend this file by filling in the "TODO" sections with real code.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Optional

# TODO: If you prefer, install the PyGithub package and use its API wrapper
# instead of raw HTTP requests via 'requests'. For the template, we keep things
# simple and leave the choice up to the implementer.


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns
    -------
    argparse.Namespace
        The parsed arguments with the attribute ``repo`` containing the
        GitHub repository URL or ``owner/repo`` string.
    """

    parser = argparse.ArgumentParser(description="Fetch GitHub repository license")
    parser.add_argument("repo", help="GitHub URL or 'owner/repo' string")
    return parser.parse_args()


def fetch_license_info(repo: str) -> Optional["LicenseInfo"]:
    """Fetch license information from the GitHub API.

    Parameters
    ----------
    repo : str
        Repository URL or ``owner/repo`` string.

    Returns
    -------
    Optional[LicenseInfo]
        Structured license data or ``None`` if the request fails.
    """
    # TODO: Use the GitHub API to request license details. You can either use
    # the endpoint ``GET /repos/{owner}/{repo}/license`` or rely on the PyGithub
    # library's helper methods.
    # - Handle HTTP errors (e.g., repository not found, rate limiting).
    # - Parse the JSON response and populate a ``LicenseInfo`` instance.

    import re
    import requests

    # Regex to extract owner and repo from various GitHub URL formats
    patterns = [
        r"github\.com/([^/]+)/([^/]+)/?.*",  # https://github.com/owner/repo
        r"([^/]+)/([^/]+)"  # owner/repo
    ]

    owner, repo_name = None, None
    for pattern in patterns:
        match = re.search(pattern, repo)
        if match:
            owner, repo_name = match.groups()[:2]  # Take the first two capturing groups
            break

    if not owner or not repo_name:
        print(f"Invalid repository format: {repo}")
        return None

    api_url = f"https://api.github.com/repos/{owner}/{repo_name}/license"

    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raise an exception for bad status codes
    except requests.exceptions.HTTPError as err:
        if response.status_code == 404:
            print(f"Repository not found or no license information: {repo}")
        elif response.status_code == 403:
            print(f"Rate limit exceeded or access forbidden for: {repo}")
        else:
            print(f"HTTP error occurred: {err}")
        return None
    except requests.exceptions.RequestException as err:
        print(f"Request failed: {err}")
        return None

    try:
        license_data = response.json()
    except ValueError:
        print("Failed to parse JSON response")
        return None

    # Assuming the license data contains 'spdx_id', 'name', and 'description'
    # The actual description might be nested or need to be fetched separately
    # For now, we'll use a placeholder if 'description' is not directly available.
    # The GitHub API provides 'license.spdx_id' and 'license.name'.
    # The description of the license (permissions, conditions, limitations)
    # is available via a separate endpoint: GET /licenses/{license}
    # For this implementation, we will use the 'name' as a placeholder for description
    # if the 'description' field is not available directly in the license object.

    if not license_data.get("license"):
        print(f"No license information found for {repo}")
        return None

    license_details = license_data["license"]
    spdx_id = license_details.get("spdx_id")
    name = license_details.get("name")

    # Fetch detailed license description
    detailed_license_info = fetch_detailed_license_description(license_details.get("key"))
    description = detailed_license_info if detailed_license_info else "Description not available."

    if not spdx_id or not name:
        print(f"SPDX ID or Name not found in license data for {repo}")
        return None

    return LicenseInfo(spdx_id=spdx_id, name=name, description=description)


def fetch_detailed_license_description(license_key: str) -> Optional[str]:
    """Fetch detailed license description from GitHub API."""
    if not license_key:
        return None

    import requests # Import requests here
    api_url = f"https://api.github.com/licenses/{license_key}"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        license_data = response.json()
        return license_data.get("description")
    except requests.exceptions.RequestException:
        return None


@dataclass
class LicenseInfo:
    """Simple data container for license details."""

    spdx_id: str
    name: str
    description: str  # short explanation of what the license allows


def describe_license(spdx_id: str, api_description: str) -> str:
    """Return a short, human-readable description of a license.

    This function can be implemented as a mapping from SPDX identifiers
    to a one-paragraph summary describing permissions, conditions, and
    limitations. For uncommon licenses, you might fetch the text and use
    an LLM to summarize it.
    """
    common_licenses = {
        "MIT": "The MIT License is a permissive free software license originating at the Massachusetts Institute of Technology (MIT). It permits reuse within proprietary software provided that all copies of the licensed software include a copy of the MIT License terms and the copyright notice. MIT licensed software can also be re-licensed under the GPL, but is not compatible with it if the GPL software is not also available under MIT terms.",
        "Apache-2.0": "The Apache License 2.0 is a permissive free software license written by the Apache Software Foundation (ASF). It allows users to use the software for any purpose, to distribute it, to modify it, and to distribute modified versions of the software under the terms of the license, without concern for royalties. The Apache License also requires that all redistributed software include a copy of the license and a notice of any significant changes made to the software.",
        "GPL-3.0": "The GNU General Public License version 3 (GPLv3) is a strong copyleft license. This means that any derivative work must also be licensed under the GPLv3. It grants recipients of a computer program the rights to run the program for any purpose, to study and modify the source code, and to distribute copies of both the original program and derivative works. It aims to prevent software from being turned into proprietary software."
    }

    return common_licenses.get(spdx_id, api_description)


def main() -> None:
    args = parse_args()

    # Normalize the repository string or URL here if needed.
    # TODO: Parse the input to extract ``owner`` and ``repo`` parts.

    license_info = fetch_license_info(args.repo)
    if not license_info:
        print("Failed to retrieve license information")
        return

    # Get the concise description
    concise_description = describe_license(license_info.spdx_id, license_info.description)

    print(f"License: {license_info.name} ({license_info.spdx_id})")
    print()
    print(concise_description)


if __name__ == "__main__":
    main()

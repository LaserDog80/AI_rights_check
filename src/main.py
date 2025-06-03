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
    raise NotImplementedError


@dataclass
class LicenseInfo:
    """Simple data container for license details."""

    spdx_id: str
    name: str
    description: str  # short explanation of what the license allows


def describe_license(spdx_id: str) -> str:
    """Return a short, human-readable description of a license.

    This function can be implemented as a mapping from SPDX identifiers
    to a one-paragraph summary describing permissions, conditions, and
    limitations. For uncommon licenses, you might fetch the text and use
    an LLM to summarize it.
    """
    # TODO: Provide summaries for common licenses (MIT, Apache-2.0, GPL-3.0, ...).
    # Optionally integrate an LLM for unknown licenses.
    raise NotImplementedError


def main() -> None:
    args = parse_args()

    # Normalize the repository string or URL here if needed.
    # TODO: Parse the input to extract ``owner`` and ``repo`` parts.

    license_info = fetch_license_info(args.repo)
    if not license_info:
        print("Failed to retrieve license information")
        return

    print(f"License: {license_info.name} ({license_info.spdx_id})")
    print()
    print(license_info.description)


if __name__ == "__main__":
    main()

"""Confirm that the commit hashes in a plugin XML exist on GitHub.

test.py only checks that <Commit> looks like hex. This asks GitHub whether
each RepoId/Commit pair resolves: the main <Commit> plus every
<AlternateVersions>/<Version>/<Commit>. Mod XMLs have no commit and pass.

Usage:
  python check_commits.py Plugins/Mirror.xml [more.xml ...]

Set GITHUB_TOKEN to raise the API rate limit (60/h unauthenticated).
Exit code 1 if any commit is missing or could not be checked.
"""
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"
API = "https://api.github.com/repos/{repo}/commits/{sha}"


def main():
	files = sys.argv[1:]
	if not files:
		print(f"Usage: {os.path.basename(__file__)} plugin.xml [plugin.xml ...]")
		sys.exit(2)

	failed = 0
	checked = 0
	for path in files:
		for repo, sha in commits_in(path):
			checked += 1
			if not report(path, repo, sha, check_commit(repo, sha)):
				failed += 1

	if failed:
		print(f"{failed} of {checked} commits missing or unchecked")
		sys.exit(1)
	print(f"All {checked} commits exist")


def commits_in(xmlFile: str):
	"""(RepoId, Commit) pairs declared by a GitHubPlugin XML; empty for mods."""
	root = ET.parse(xmlFile).getroot()
	if root.attrib.get(XSI_TYPE) != "GitHubPlugin":
		return []
	repo = text_of(root.find("RepoId"))
	if not repo:
		raise Exception(f"{xmlFile} is missing a RepoId")
	pairs = []
	sha = text_of(root.find("Commit"))
	if sha:
		pairs.append((repo, sha))
	for version in root.findall("AlternateVersions/Version"):
		sha = text_of(version.find("Commit"))
		if sha and (repo, sha) not in pairs:
			pairs.append((repo, sha))
	return pairs


def text_of(element):
	return element.text.strip() if element is not None and element.text else None


def check_commit(repo: str, sha: str):
	"""True if GitHub knows the commit, False if not, or an error string."""
	request = urllib.request.Request(API.format(repo=repo, sha=sha), headers=headers())
	try:
		with urllib.request.urlopen(request, timeout=30) as response:
			return response.status == 200
	except urllib.error.HTTPError as error:
		if error.code in (404, 422):
			return False
		return f"HTTP {error.code}: {error.reason}"
	except urllib.error.URLError as error:
		return f"network error: {error.reason}"


def headers():
	result = {"Accept": "application/vnd.github+json", "User-Agent": "PluginHub-check-commits"}
	token = os.environ.get("GITHUB_TOKEN")
	if token:
		result["Authorization"] = f"Bearer {token}"
	return result


def report(path: str, repo: str, sha: str, result):
	if result is True:
		print(f"OK       {path}: {repo}@{sha}")
		return True
	if result is False:
		print(f"MISSING  {path}: {repo}@{sha}")
		return False
	print(f"ERROR    {path}: {repo}@{sha}: {result}")
	return False


if __name__ == "__main__":
	main()

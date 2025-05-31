import re
import requests

def version_tuple(version_str):
    version_str = version_str.lstrip("v").split("-")[0]
    return tuple(map(int, (version_str.split("."))))

def get_supported_releases():
    min_version = (1, 0, 0)
    api_url = "https://api.github.com/repos/mechawrench/wificom-lib/releases"
    response = requests.get(api_url)
    response.raise_for_status()
    releases = response.json()
    version_regex = re.compile(r"v\d+\.\d+\.\d+")
    supported_releases = [r for r in releases if version_regex.match(r["tag_name"]) and version_tuple(r["tag_name"]) >= min_version]
    return supported_releases

def get_latest_release():
    for release in get_supported_releases():
        if not release["prerelease"]:
            return release
    return None

def get_specific_commit(commit_ref):
    api_url = "https://api.github.com/repos/mechawrench/wificom-lib/commits/" + commit_ref
    response = requests.get(api_url)
    response.raise_for_status()
    return response.json()

def get_sources_json(commit_ref):
    url = "https://raw.githubusercontent.com/mechawrench/wificom-lib/" + commit_ref + "/sources.json"
    print("Downloading", url)
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

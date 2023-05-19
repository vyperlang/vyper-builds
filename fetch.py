import datetime
import requests
import zipfile
import sys
import os
import io

if __name__ == "__main__":

    # use token not for permissions but because it improves rate limiting
    TOKEN = os.environ["GITHUB_TOKEN"]

    s = requests.Session()
    s.headers["Accept"] = "application/vnd.github+json"
    s.headers["Authorization"] = f"Bearer {TOKEN}"

    def URL(uri):
        return f"https://api.github.com/repos/vyperlang/vyper{uri}"

    r = s.get(URL("/actions/artifacts?per_page=100"))
    r.raise_for_status()
    artifacts = r.json()["artifacts"]

    r = s.get(URL("/releases?per_page=100"))
    r.raise_for_status()
    releases = r.json()

    changes = 0

    for a in artifacts:
        workflow_run = a["workflow_run"]["id"]
        r = s.get(URL(f"/actions/runs/{workflow_run}"))
        r.raise_for_status
        workflow_info = r.json()

        commit_info = workflow_info["head_commit"]
        commit_time = datetime.datetime.fromisoformat(commit_info["timestamp"])
        commit_hash = commit_info["id"]
        short_commit_hash = commit_hash[:16]

        # sorted by time of day.
        commit_id = commit_time.strftime("%H:%M:%SZ-") + short_commit_hash

        if workflow_info["event"] != "push":
            print(f"run {workflow_run} ({commit_id}) is not a push to master", file=sys.stderr)
            continue
        if workflow_info["status"] != "completed":
            print(f"run {workflow_run} ({commit_id}) is not complete", file=sys.stderr)
            continue
        if workflow_info["conclusion"] != "success":
            print(f"run {workflow_run} ({commit_id}) was not successful", file=sys.stderr)
            continue
        if workflow_info["head_branch"] != "master":
            print(f"run {workflow_run} ({commit_id}) is not master", file=sys.stderr)
            continue
        if a["expired"] is True:
            print(f"run {workflow_run} ({commit_id}) expired", file=sys.stderr)
            continue

        # extract into ./builds/2023/03/30/12:30:05Z-6307049f071a8f5857777c87bb5d858d28112acf/
        date_part = commit_time.strftime("%Y/%m/%d")
        directory_part = f"{date_part}/{commit_id}/"
        output_directory = f"builds/{directory_part}/"
        tmp_directory = f"tmp/{date_part}/"

        if os.path.exists(output_directory):
            print(f"{output_directory} exists, skipping...", file=sys.stderr)
            continue

        print(f"fetching {directory_part} ...", file=sys.stderr)
        artifact_id = a["id"]
        r = s.get(URL(f"/actions/artifacts/{artifact_id}/zip"))
        r.raise_for_status()

        os.makedirs(tmp_directory, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            print(f"extracting to {tmp_directory} ...", file=sys.stderr)
            z.extractall(tmp_directory)

        os.makedirs(os.path.dirname(output_directory))

        os.rename(tmp_directory, output_directory)
        print(f"successfully fetched {output_directory}", file=sys.stderr)

        changes += 1

    for release in releases:
        tag_name = release["tag_name"]
        output_dir = f"releases/{tag_name}"
        os.makedirs(output_dir, exist_ok=True)

        for asset in release["assets"]:
            filename = asset["name"]
            if os.exists(target_path):
                print(f"{target_path} exists, skipping ...", file=sys.stderr)
            print(f"fetching {filename}", file=sys.stderr)
            r = s.get(asset["browser_download_url"])
            r.raise_for_status()
            target_path = f"{output_dir}/{filename}"
            with open(target_path, "wb") as f:
                f.write(r.content)
            print(f"{filename} fetched to {target_path}", file=sys.stderr)
            changes += 1

    if changes == 0:
        print("No files fetched.", file=sys.stderr)
        os.exit(1)

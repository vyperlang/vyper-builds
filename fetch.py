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

    changes = 0

    for a in artifacts:
        workflow_run = a["workflow_run"]["id"]
        r = s.get(URL(f"/actions/runs/{workflow_run}"))
        r.raise_for_status
        workflow_info = r.json()

        if workflow_info["event"] != "push":
            print(f"run {workflow_run} is not a push to master", file=sys.stderr)
            continue
        if workflow_info["status"] != "completed":
            print(f"run {workflow_run} is not complete", file=sys.stderr)
            continue
        if workflow_info["conclusion"] != "success":
            print(f"run {workflow_run} was not successful", file=sys.stderr)
            continue
        if workflow_info["head_branch"] != "master":
            print(f"run {workflow_run} is not master", file=sys.stderr)
            continue

        commit_info = workflow_info["head_commit"]
        commit_time = datetime.datetime.fromisoformat(commit_info["timestamp"])
        commit_hash = commit_info["id"]
        short_commit_hash = commit_hash[12:]

        # sorted by time of day.
        commit_id = commit_time.strftime("%H:%M:%SZ-") + short_commit_hash
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
        r = s.get(URL(f"/actions/artifacts/{artifact_id}/zip"), stream=True)
        r.raise_for_status()

        os.makedirs(tmp_directory, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            print(f"extracting to {tmp_directory} ...", file=sys.stderr)
            z.extractall(tmp_directory)

        os.makedirs(os.path.dirname(output_directory))

        os.rename(tmp_directory, output_directory)
        print(f"successfully fetched {output_directory}", file=sys.stderr)

        changes += 1

    if changes == 0:
        print("No files fetched.", file=sys.stderr)
        os.exit(1)

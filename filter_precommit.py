"""
HOW TO USE:
1. Save the script at your folder ex: ~/working/filter_precommit.py
2. Add this alias to your shell config:
alias filter_precommit='SKIP=django-migrations git commit 2>&1 | tee ~/working/git_output.log; python ~/working/filter_precommit.py'
3. Run filter_precommit when committing
"""

import subprocess
import sys
import re
from typing import Dict, Set
import os

output_path = os.path.expanduser("~/working/git_output.log")

def get_changed_lines() -> Dict[str, Set[int]]:
    """Get the line numbers changed in staged files."""
    try:
        result = subprocess.run(
            ["git", "diff", "--staged"],
            capture_output=True,
            text=True,
            check=True
        )
        diff_output = result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error getting git diff: {e}", file=sys.stderr)
        sys.exit(1)

    changed_lines = {}
    current_file = None
    current_line = 0  # Track the actual current line number in the file
    
    for line in diff_output.splitlines():
        # Match file names in diff (e.g., "+++ b/src/main.py")
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()  # Remove "+++ b/"
            changed_lines[current_file] = set()
            current_line = 0  # Reset line counter for new file
        # Match line number ranges (e.g., "@@ -start,count +start,count @@")
        elif line.startswith("@@"):
            match = re.match(r"@@ -\d+,\d+ \+(\d+),\d+ @@", line)
            if match and current_file:
                # The line number in the diff is the starting line in the current file
                current_line = int(match.group(1))
        # Track new lines (starting with "+")
        elif line.startswith("+") and current_file and not line.startswith("+++"):
            changed_lines[current_file].add(current_line)
            current_line += 1
        # Track unchanged or deleted lines to keep line count accurate
        elif line.startswith(" ") or line.startswith("-"):
            current_line += 1

    return changed_lines

def read_saved_logs(log_file: str) -> list[str]:
    """Read logs from a saved file."""
    try:
        with open(log_file, 'r') as f:
            return f.read().splitlines()
    except FileNotFoundError:
        print(f"Log file {log_file} not found.", file=sys.stderr)
        sys.exit(1)

def filter_logs(logs: list[str], changed_lines: Dict[str, Set[int]]) -> list[str]:
    """Filter logs to include only lines referencing changed line numbers."""
    if not changed_lines:
        return []

    filtered = []
    # Regex to match logs like "file:line:col: message" or "file:line: message"
    log_pattern = re.compile(r"^(.*?):(\d+):(?:\d+:)?\s*(.*)$")

    for log in logs:
        match = log_pattern.match(log)
        if match:
            file_path, line_num, message = match.groups()
            file_path = file_path.strip()
            file_path = file_path[file_path.index("src/"):] # get relative path (from src) 
            line_num = int(line_num)
            # Check if the file and line number match a changed line
            if file_path in changed_lines and line_num in changed_lines[file_path]:
                filtered.append(log)
        # Include non-line-specific logs for changed files (e.g., "black: Reformatted src/main.py")
        elif any(file_path in log for file_path in changed_lines):
            filtered.append(log)

    return filtered

def main():
    print("======== Getting changed lines =============")
    changed_lines = get_changed_lines()
    if not changed_lines:
        print("No staged files or changed lines to process.", file=sys.stderr)
        sys.exit(0)

    logs = read_saved_logs(output_path)
    filtered_logs = filter_logs(logs, changed_lines)

    print("======== Filtered Logs =============")
    if filtered_logs:
        print("\n".join(filtered_logs))
    else:
        print("No logs found for changed lines in staged files.")

if __name__ == "__main__":
    main()

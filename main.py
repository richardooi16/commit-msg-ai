"""
This script makes a call to openAI to create a commit message
based on the git diff in the repo.
"""
import subprocess
import sys
import os
from openai import OpenAI
from openai import OpenAIError
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

MODEL_NAME = "gpt-4o-mini"
INSTRUCTIONS = """Write a commit message based on the git diff and git branch provided.
The format used should start with the type (feat, fix, chore), followed by the commit message. 
At the end, add the git branch name to the end of the message." 
The format for the commit should be:" 
'\\{type\\}: {commit message} - {branch name}'"""

class GitOperationError(Exception):
    """Custom error class for git related issues"""

class AIOperationError(Exception):
    """Custom error class for OpenAI related issues"""

class UserAbortError(Exception):
    """Custom error class for user aborting"""

def get_git_branch() -> str:
    """Gets the current Git branch name."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
            errors="ignore"
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitOperationError(f"Error getting git branch: {e.stderr or e}") from e

def get_staged_changes() -> str:
    """Gets the staged Git changes (diff)."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached"],
            check=True,
            capture_output=True,
            text=True,
            errors="ignore"
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitOperationError(f"Error getting git diff: {e.stderr or e}") from e

def generate_commit_msg(changes: str, branch_name: str) -> str | None:
    """
    Generates a commit message based on git diff and branch name using an AI model.
    Returns the generated message or None if generation fails.
    """
    if not changes:
        raise AIOperationError("No changes staged to commit. Nothing to generate a message for.")

    prompt_input = f"Git Diff:\n{changes}\n\nBranch: {branch_name}"

    try:
        response = client.responses.create(
            model=MODEL_NAME,
            instructions=INSTRUCTIONS,
            input=prompt_input
        )
        return response.output_text.strip()
    except OpenAIError as e:
        raise OpenAIError(f"Error generating commit message from AI: {e}") from e

def prompt_user(message: str) -> str:
    """
    Prompts the user to accept, remake, or reject the commit message.
    Returns "Y" for yes, "R" for remake, "Q" for quit.
    Keeps prompting until a valid option is chosen.
    """
    while True:
        print("\nGenerated commit message:")
        print("=========================================")
        print(message)
        print("=========================================")
        print("Are you sure you want to accept this?\n")
        user_input = input("Yes (Y) Remake (R) Quit (Q)  ").strip().upper()

        if user_input in ("Y", "R", "Q"):
            return user_input
        else:
            print("Invalid input. Please enter Y, R, or Q.")

def perform_git_commit(message: str) -> bool:
    """Performs the git commit with the given message."""
    try:
        subprocess.run(
            ["git", "commit", "-m", message],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        raise GitOperationError(f"\nError during git commit: {e.stderr or e}") from e

def commit_process():
    """Main process for generating and committing a message."""
    staged_changes = get_staged_changes()
    current_branch = get_git_branch()
    accepted = False
    while not accepted:
        print("\nGenerating commit message...")
        generated_message = generate_commit_msg(staged_changes, current_branch)
        user_choice = prompt_user(generated_message)
        if user_choice == "Y":
            perform_git_commit(generated_message)
            print("\nCommit successful!")
            accepted = True
        elif user_choice == "Q":
            raise UserAbortError("Aborting.")
        # If user_choice == "R", continue

if __name__ == '__main__':
    # Check if currently in a git repository
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            check=True,
            capture_output=True,
            text=True
        )
    except subprocess.CalledProcessError:
        print("\nNot in a git repository. Aborting.", file=sys.stderr)
        sys.exit(1)

    try:
        commit_process()
        sys.exit(0)
    except GitOperationError as e:
        print(f"\nGit operation failed: {e}", file=sys.stderr)
        sys.exit(1)
    except AIOperationError as e:
        print(f"\nAI operation failed: {e}", file=sys.stderr)
        sys.exit(1)
    except UserAbortError as e:
        print(e)
        sys.exit(0)
    except Exception as e:
        print(f"An unexpected error has occured: {e}", file=sys.stderr)
        sys.exit(1)

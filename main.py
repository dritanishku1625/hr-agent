from pathlib import Path

from hr_agent.agent import load_local_env, review_all


def main() -> None:
    load_local_env(Path(".env"))
    review_all()


if __name__ == "__main__":
    main()

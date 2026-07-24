import argparse
import asyncio
import json

from workers.ingestion.runner import run_sync


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["openai", "sec"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(run_sync(source=args.source, force=args.force))
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

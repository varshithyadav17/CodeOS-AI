"""Write the confirmed Render origin into Vercel's static API proxy config."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit


def configure(origin: str, output: Path) -> None:
    parsed = urlsplit(origin)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ValueError("Provide an HTTPS origin without credentials, path, query, or fragment.")
    config = json.loads(output.read_text())
    config["rewrites"] = [
        {"source": "/api/:path*", "destination": f"https://{parsed.netloc}/api/:path*"},
        *[rule for rule in config.get("rewrites", []) if rule.get("source") != "/api/:path*"],
    ]
    output.write_text(json.dumps(config, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin", help="Confirmed HTTPS origin of the existing Render service")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "frontend/vercel.json")
    args = parser.parse_args()
    try:
        configure(args.origin, args.output)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print("Vercel API destination configured. Commit this config before deploying.")

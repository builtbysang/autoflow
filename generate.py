"""Fully automated image generation pipeline.

Usage:
  python3 generate.py "a woman in a red dress, editorial fashion"
  python3 generate.py "product shot of white sneakers" --aspect portrait --out ~/Desktop/photos
  python3 generate.py "..." --out ~/Documents/Projects/MyProject/images

Config (~/.autoflow.json):
  {
    "default_out": "~/Pictures/autoflow",
    "default_tier": "PAYGATE_TIER_ONE"
  }
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE_URL = "http://localhost:8100"
CONFIG_PATH = Path.home() / ".autoflow.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE_URL + path, timeout=30) as r:
        return json.loads(r.read())


def poll(request_id: int, timeout: int = 180) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = get(f"/api/requests/{request_id}")
        status = result.get("status")
        if status == "done":
            return result
        if status == "failed":
            print(f"[error] {result.get('error')}")
            sys.exit(1)
        print(f"  waiting... ({status})")
        time.sleep(3)
    print("[error] timed out")
    sys.exit(1)


def resolve_out(out_arg: str | None, cfg: dict) -> Path:
    """Resolve output folder: CLI arg > config default > ~/Pictures/autoflow."""
    raw = out_arg or cfg.get("default_out") or "~/Pictures/autoflow"
    path = Path(raw).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def main():
    cfg = load_config()

    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="?", default="", help="Image prompt")
    parser.add_argument("--aspect", default="landscape", choices=["landscape", "portrait", "square"])
    parser.add_argument("--tier", default=cfg.get("default_tier", "PAYGATE_TIER_ONE"),
                        choices=["PAYGATE_TIER_ONE", "PAYGATE_TIER_TWO"],
                        help="Flow tier: ONE=Pro, TWO=Ultra")
    parser.add_argument("--project", default=None, help="Google Flow project name (default: output folder name)")
    parser.add_argument("--out", default=None,
                        help="Output folder (default: config default_out or ~/Pictures/autoflow)")
    parser.add_argument("--set-out", default=None,
                        help="Save a new default output folder to ~/.autoflow.json")
    args = parser.parse_args()

    # Handle config update
    if args.set_out:
        cfg["default_out"] = str(Path(args.set_out).expanduser())
        save_config(cfg)
        print(f"[config] default output folder set to: {cfg['default_out']}")
        if not args.prompt:
            return

    aspect_map = {
        "landscape": "IMAGE_ASPECT_RATIO_LANDSCAPE",
        "portrait":  "IMAGE_ASPECT_RATIO_PORTRAIT",
        "square":    "IMAGE_ASPECT_RATIO_SQUARE",
    }

    out_dir = resolve_out(args.out, cfg)

    # Project name = CLI arg > output folder name > "autoflow"
    project_name = args.project or out_dir.name or "autoflow"

    # 1. Check backend
    try:
        health = get("/api/health")
    except Exception:
        print("[error] Backend không chạy. Khởi động trước:\n  cd agent && uvicorn flowboard.main:app --port 8100")
        sys.exit(1)

    if not health.get("extension_connected"):
        print("[warn] Chrome extension chưa kết nối.")
    if not health.get("ws_stats", {}).get("flow_key_present"):
        print("[warn] Chưa có Flow token — mở labs.google/fx/tools/flow trong Chrome.")

    # 2. Create project
    print(f"[1/3] Tạo project '{project_name}'...")
    req = post("/api/requests", {"type": "create_project", "params": {"name": project_name}})
    result = poll(req["id"])
    project_id = result.get("result", {}).get("project_id") or result.get("result", {}).get("id")
    if not project_id:
        print(f"[error] Không lấy được project_id: {result}")
        sys.exit(1)
    print(f"  project_id: {project_id}")

    # 3. Gen image
    prompt = args.prompt.strip()
    if not prompt:
        print("[error] Cần nhập prompt. Ví dụ:\n  python3 generate.py \"a woman in red\"")
        sys.exit(1)

    print(f"[2/3] Generating: '{prompt}'...")
    req = post("/api/requests", {
        "type": "gen_image",
        "params": {
            "prompt": prompt,
            "project_id": project_id,
            "aspect_ratio": aspect_map[args.aspect],
            "paygate_tier": args.tier,
        }
    })
    result = poll(req["id"])

    # 4. Save output
    entries = result.get("result", {}).get("media_entries") or []
    if not entries:
        print(f"[error] Không có ảnh trong kết quả: {result}")
        sys.exit(1)

    print(f"[3/3] Lưu {len(entries)} ảnh vào {out_dir}/...")
    saved = []
    for i, entry in enumerate(entries):
        media_id = entry.get("media_id") or entry.get("id")
        url = entry.get("url")
        if url:
            fname = out_dir / f"image_{i+1}_{media_id}.jpg"
            urllib.request.urlretrieve(url, fname)
            print(f"  saved: {fname}")
            saved.append(str(fname))
        else:
            print(f"  [warn] entry {i+1} không có URL")

    print("Done.")
    # Print saved paths on last line for skill parsing
    print("SAVED:" + "|".join(saved))


if __name__ == "__main__":
    main()

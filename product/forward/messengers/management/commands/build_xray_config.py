"""دستور مدیریتی برای ساخت xray_config.json چندنودی با تست واقعی تک‌تک نودها روی api.telegram.org."""

import base64
import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from product.forward.messengers.telegram_proxy import (
    XRAY_BIN_PATH,
    ensure_telegram_proxy,
    restart_telegram_proxy,
)


def _decode_subscription_text(raw_text: str) -> List[str]:
    """استخراج خطوط لینک vless:// از متن خام یا محتوای Base64 سابسکریپشن."""
    cleaned = raw_text.strip()
    if "vless://" not in cleaned:
        try:
            padded = cleaned + "=" * (-len(cleaned) % 4)
            cleaned = base64.b64decode(padded).decode("utf-8", errors="ignore")
        except Exception:
            pass
    return [line.strip() for line in cleaned.splitlines() if line.strip().startswith("vless://")]


def _parse_vless_uri(uri: str, tag: str) -> Dict[str, Any]:
    """تبدیل لینک vless:// (با پشتیبانی از raw، xhttp، ws، grpc و reality/tls) به outbound استاندارد Xray."""
    parsed = urlparse(uri.strip())
    if parsed.scheme != "vless" or not parsed.username or not parsed.hostname or not parsed.port:
        raise ValueError(f"لینک VLESS نامعتبر است: {uri[:40]}...")

    qs = {k: v[0] for k, v in parse_qs(parsed.query, keep_blank_values=True).items()}
    network = (qs.get("type") or "raw").lower()
    if network == "tcp":
        network = "raw"

    user_obj: Dict[str, Any] = {
        "id": unquote(parsed.username),
        "encryption": qs.get("encryption") or "none",
    }
    if qs.get("flow"):
        user_obj["flow"] = qs["flow"]

    stream_settings: Dict[str, Any] = {"network": network}

    if network == "xhttp":
        xhttp_cfg: Dict[str, Any] = {}
        if qs.get("path"):
            xhttp_cfg["path"] = unquote(qs["path"])
        if qs.get("host"):
            xhttp_cfg["host"] = unquote(qs["host"])
        if qs.get("mode"):
            xhttp_cfg["mode"] = qs["mode"]
        if xhttp_cfg:
            stream_settings["xhttpSettings"] = xhttp_cfg
    elif network == "ws":
        ws_cfg: Dict[str, Any] = {}
        if qs.get("path"):
            ws_cfg["path"] = unquote(qs["path"])
        if qs.get("host"):
            ws_cfg["headers"] = {"Host": unquote(qs["host"])}
        if ws_cfg:
            stream_settings["wsSettings"] = ws_cfg
    elif network == "grpc":
        grpc_cfg: Dict[str, Any] = {}
        if qs.get("serviceName"):
            grpc_cfg["serviceName"] = unquote(qs["serviceName"])
        if grpc_cfg:
            stream_settings["grpcSettings"] = grpc_cfg

    security = (qs.get("security") or "none").lower()
    stream_settings["security"] = security
    if security == "reality":
        stream_settings["realitySettings"] = {
            "serverName": qs.get("sni") or parsed.hostname,
            "fingerprint": qs.get("fp") or "chrome",
            "publicKey": qs.get("pbk", ""),
            "shortId": qs.get("sid", ""),
            "spiderX": unquote(qs.get("spx", "")),
        }
    elif security == "tls":
        tls_cfg: Dict[str, Any] = {
            "serverName": qs.get("sni") or parsed.hostname,
            "fingerprint": qs.get("fp") or "chrome",
        }
        if qs.get("alpn"):
            tls_cfg["alpn"] = [a.strip() for a in unquote(qs["alpn"]).split(",") if a.strip()]
        stream_settings["tlsSettings"] = tls_cfg

    return {
        "tag": tag,
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": parsed.hostname,
                    "port": int(parsed.port),
                    "users": [user_obj],
                }
            ]
        },
        "streamSettings": stream_settings,
    }


def _find_free_port() -> int:
    """یافتن یک پورت آزاد لوکال برای تست تک‌تک نودها."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _probe_single_outbound(ob: Dict[str, Any], timeout_sec: float = 4.5) -> Optional[int]:
    """تست واقعی یک نود با Xray روی https://api.telegram.org و برگرداندن زمان پاسخ به میلی‌ثانیه."""
    vnext = ob["settings"]["vnext"][0]
    if vnext["port"] <= 1 or vnext["address"] in ("127.0.0.1", "localhost", "0.0.0.0"):
        return None

    test_port = _find_free_port()
    cfg = {
        "log": {"loglevel": "none"},
        "inbounds": [
            {
                "port": test_port,
                "listen": "127.0.0.1",
                "protocol": "mixed",
                "settings": {"auth": "noauth", "udp": False},
            }
        ],
        "outbounds": [ob],
    }

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=True, encoding="utf-8") as tf:
        json.dump(cfg, tf)
        tf.flush()
        proc = subprocess.Popen(
            [str(XRAY_BIN_PATH), "run", "-c", tf.name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            # صبر تا پورت موقت باز شود
            for _ in range(20):
                try:
                    with socket.create_connection(("127.0.0.1", test_port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.05)

            proxies = {
                "http": f"http://127.0.0.1:{test_port}",
                "https": f"http://127.0.0.1:{test_port}",
            }
            t0 = time.monotonic()
            resp = requests.get("https://api.telegram.org", proxies=proxies, timeout=timeout_sec)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            if resp.status_code in (200, 301, 302):
                return elapsed_ms
        except Exception:
            return None
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
    return None


def build_multinode_config(uris: List[str], port: int = 10808, stdout=None) -> Dict[str, Any]:
    """ساخت xray_config.json با فیلتر کردن نودهای خراب و مرتب‌سازی بر اساس سرعت به api.telegram.org."""
    if not XRAY_BIN_PATH.exists():
        ensure_telegram_proxy()

    candidates: List[Tuple[int, Dict[str, Any]]] = []
    for idx, uri in enumerate(uris, start=1):
        try:
            ob = _parse_vless_uri(uri, tag=f"raw-{idx}")
        except ValueError:
            continue

        net = ob["streamSettings"]["network"]
        if XRAY_BIN_PATH.exists():
            ms = _probe_single_outbound(ob)
            if ms is not None:
                candidates.append((ms, ob))
                if stdout:
                    stdout.write(f"  [OK] #{idx} ({net}) -> {ms} ms")
            else:
                # نود را حذف نمی‌کنیم؛ در انتهای لیست می‌ماند تا observatory هر ۳۰ ثانیه دوباره تستش کند
                candidates.append((999999, ob))
                if stdout:
                    stdout.write(f"  [STANDBY] #{idx} ({net}) -> timeout/kept at end")
        else:
            candidates.append((9999, ob))

    if not candidates:
        raise CommandError("هیچ نودی نتوانست با موفقیت به api.telegram.org متصل شود.")

    candidates.sort(key=lambda item: item[0])

    outbounds: List[Dict[str, Any]] = []
    for idx, (_ms, ob) in enumerate(candidates, start=1):
        ob["tag"] = f"proxy-{idx}"
        outbounds.append(ob)

    return {
        "log": {"loglevel": "warning"},
        "observatory": {
            "subjectSelector": ["proxy-"],
            "probeUrl": "https://api.telegram.org",
            "probeInterval": "30s",
            "enableConcurrency": True,
        },
        "inbounds": [
            {
                "tag": "mixed-in",
                "port": port,
                "listen": "127.0.0.1",
                "protocol": "mixed",
                "settings": {"auth": "noauth", "udp": True},
            }
        ],
        "outbounds": outbounds,
        "routing": {
            "domainStrategy": "AsIs",
            "balancers": [
                {
                    "tag": "tg-balancer",
                    "selector": ["proxy-"],
                    "fallbackTag": outbounds[0]["tag"],
                    "strategy": {"type": "leastPing"},
                }
            ],
            "rules": [
                {
                    "type": "field",
                    "inboundTag": ["mixed-in"],
                    "balancerTag": "tg-balancer",
                }
            ],
        },
    }


class Command(BaseCommand):
    """ساخت و فعال‌سازی کانفیگ چندنودی Xray با تست تک‌تک نودها روی تلگرام."""

    help = "ساخت xray_config.json چندنودی با فیلتر نودهای خراب و مرتب‌سازی بر اساس سرعت به تلگرام"

    def add_arguments(self, parser):
        parser.add_argument("--sub-url", help="لینک سابسکریپشن V2Ray")
        parser.add_argument("--file", help="مسیر فایل متنی حاوی لینک‌های vless:// (هر خط یک لینک)")
        parser.add_argument("--stdin", action="store_true", help="خواندن لینک‌های vless:// از ورودی استاندارد")

    def handle(self, *args, **options):
        raw_text = ""
        if options.get("sub_url"):
            self.stdout.write("Fetching subscription...")
            resp = requests.get(options["sub_url"], timeout=20)
            resp.raise_for_status()
            raw_text = resp.text
        elif options.get("file"):
            raw_text = Path(options["file"]).read_text(encoding="utf-8")
        elif options.get("stdin"):
            self.stdout.write("Paste vless:// links and press Ctrl+D:")
            raw_text = sys.stdin.read()
        else:
            raise CommandError("یکی از گزینه‌های --sub-url یا --file یا --stdin را مشخص کنید.")

        uris = _decode_subscription_text(raw_text)
        if not uris:
            raise CommandError("هیچ لینک vless:// معتبری پیدا نشد.")

        self.stdout.write(f"Testing {len(uris)} nodes directly against api.telegram.org...")
        config_data = build_multinode_config(uris, stdout=self.stdout)
        out_path = Path(settings.BASE_DIR) / "product" / "forward" / "bin" / "xray_config.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(config_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ همه {len(config_data['outbounds'])} نود از سریع‌ترین به کندترین مرتب و ذخیره شدند."
            )
        )

        if restart_telegram_proxy():
            self.stdout.write(self.style.SUCCESS("🚀 Xray با نودهای فیلترشده و سوییچ خودکار ری‌استارت و فعال شد."))
        else:
            raise CommandError("ری‌استارت Xray ناموفق بود؛ لاگ /tmp/xray_runtime/xray.log را بررسی کنید.")

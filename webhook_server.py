"""
Wani AI Voice Studio - Razorpay Webhook Daemon Server
=====================================================
Production-grade, concurrent HTTP webhook endpoint listening for
Razorpay Subscriptions events.

Endpoints:
- POST /api/webhook/razorpay : Process verified incoming Razorpay webhooks
- GET  /health               : Liveness & health check
"""

import sys
import json
import logging
import argparse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from subscription_manager import SubscriptionManager, get_now_ist, format_iso

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("WaniWebhookServer")

class RazorpayWebhookHandler(BaseHTTPRequestHandler):
    server_version = "WaniWebhookDaemon/1.0"

    def do_GET(self):
        if self.path in ["/health", "/", "/api/webhook/health"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "status": "healthy",
                "service": "Wani Razorpay Subscriptions Webhook Daemon",
                "timestamp": format_iso(get_now_ist())
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path in ["/api/webhook/razorpay", "/webhook/razorpay", "/api/razorpay/webhook"]:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Empty body"}).encode("utf-8"))
                return

            raw_body = self.rfile.read(content_length)
            signature = self.headers.get("X-Razorpay-Signature", "")
            event_id = self.headers.get("X-Razorpay-Event-Id", None)

            sm = SubscriptionManager()
            success, message, status_code = sm.process_webhook(
                raw_body=raw_body,
                signature=signature,
                event_id=event_id
            )

            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response_payload = {
                "success": success,
                "message": message,
                "status_code": status_code,
                "timestamp": format_iso(get_now_ist())
            }
            self.wfile.write(json.dumps(response_payload).encode("utf-8"))
            logger.info("Webhook %s: %s (HTTP %d)", "Processed" if success else "Rejected", message, status_code)
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))

    def log_message(self, format, *args):
        # Override default noisy stderr logging
        pass

def run_server(port: int = 8504, host: str = "0.0.0.0"):
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, RazorpayWebhookHandler)
    logger.info("Starting Wani Razorpay Webhook Server on %s:%d", host, port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down webhook server...")
        httpd.server_close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wani Razorpay Webhook Daemon")
    parser.add_argument("--port", type=int, default=8504, help="Port to listen on (default: 8504)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    args = parser.parse_args()
    run_server(port=args.port, host=args.host)

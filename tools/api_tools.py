import json
import urllib.request
import urllib.error


async def call_api(args: dict) -> dict:
    url = args["url"]
    method = args.get("method", "GET").upper()
    body = args.get("body", "").encode() if args.get("body") else None

    headers = {}
    if args.get("headers"):
        try:
            headers = json.loads(args["headers"])
        except json.JSONDecodeError:
            return {"content": [{"type": "text", "text": "Error: headers must be valid JSON"}], "isError": True}

    try:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            response_body = resp.read().decode("utf-8", errors="replace")
            return {"content": [{"type": "text", "text": f"Status: {resp.status}\n\n{response_body[:5000]}"}]}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        return {"content": [{"type": "text", "text": f"HTTP Error {e.code}: {body_text[:2000]}"}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}

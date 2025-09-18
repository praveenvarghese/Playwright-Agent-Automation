# common/mcp_pack.py
from typing import Any, Dict, List

def build_simple_pack(mcp_log: List[Dict[str, Any]]) -> Dict[str, Any]:
    actions = []
    assertions = []

    for e in mcp_log:
        t, args = e.get("tool",""), e.get("args",{}) or {}

        if t == "browser_navigate":
            item = {"tool":"navigate", "to": args.get("url")}
            if e.get("current_url"):
                item["after"] = e["current_url"]
                assertions.append({"type":"url","expected": e["current_url"]})
            actions.append(item)

        elif t == "browser_fill_form":
            fields = [
                {"name": f.get("name"), "type": f.get("type"), "ref": f.get("ref")}
                for f in (args.get("fields") or [])
            ]
            actions.append({"tool":"fill_form", "fields": fields})

        elif t == "browser_type":
            item = {"tool":"type", "el": args.get("element"), "ref": args.get("ref")}
            if args.get("submit"): item["submit"] = True
            actions.append(item)

        elif t == "browser_click":
            actions.append({"tool":"click", "el": args.get("element"), "ref": args.get("ref")})

        elif t == "browser_hover":
            actions.append({"tool":"hover", "el": args.get("element"), "ref": args.get("ref")})

        elif t == "browser_snapshot":
            actions.append({"tool":"snapshot"})

        else:
            actions.append({"tool": t, "args": args})

    return {"actions": actions, "assertions": assertions}

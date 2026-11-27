import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post_short as P
ints = P.call("GET", "/integrations"); ints = ints if isinstance(ints, list) else ints.get("integrations", [])
for i in ints:
    print(json.dumps({k: i.get(k) for k in ("name", "identifier", "providerIdentifier", "profile", "disabled", "refreshNeeded", "inBetweenSteps", "id")}))

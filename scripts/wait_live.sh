#!/bin/bash
# Wait until a successful Cloudflare Pages deploy of the "manifest" project contains the given commit, then print it.
#   bash scripts/wait_live.sh <commit>
# Needs a Cloudflare API token on the request (in Claude Code cloud sessions the proxy adds it; elsewhere set
# CF_API_TOKEN). The account id is looked up, not stored, because this repository is public.
C=${1:?usage: wait_live.sh <commit>}
H=(-H "Authorization: Bearer ${CF_API_TOKEN:-x}")
ACC=${CF_ACCOUNT_ID:-}
if [ -z "$ACC" ]; then   # the token can see several accounts: take the one that has the Pages project "manifest"
  for a in $(curl -s "https://api.cloudflare.com/client/v4/accounts" "${H[@]}" | python3 -c "import sys,json; [print(x['id']) for x in (json.load(sys.stdin).get('result') or [])]"); do
    if curl -s "https://api.cloudflare.com/client/v4/accounts/$a/pages/projects/manifest" "${H[@]}" | python3 -c "import sys,json; sys.exit(0 if json.load(sys.stdin).get('success') else 1)"; then ACC=$a; break; fi
  done
fi
[ -n "$ACC" ] || { echo "no Cloudflare account visible"; exit 1; }
cd "$(git rev-parse --show-toplevel)" || exit 1
for i in $(seq 1 45); do
  git fetch -q origin main 2>/dev/null
  for h in $(curl -s "https://api.cloudflare.com/client/v4/accounts/$ACC/pages/projects/manifest/deployments?per_page=10" "${H[@]}" | python3 -c "
import sys,json
for x in json.load(sys.stdin).get('result',[]):
    if x['latest_stage']['name']=='deploy' and x['latest_stage']['status']=='success': print(x.get('deployment_trigger',{}).get('metadata',{}).get('commit_hash',''))"); do
    if git merge-base --is-ancestor "$C" "$h" 2>/dev/null; then echo "live in ${h:0:8}"; exit 0; fi
  done
  sleep 20
done
echo "not live after 15 min"; exit 1

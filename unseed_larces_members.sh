#!/usr/bin/env bash
# =============================================================================
# unseed_larces_members.sh
#
# Removes the 19 members created by seed_larces_members.sh:
#   1. Removes each member from the LARCES lab
#   2. Deactivates each member account
#
# Usage:
#   chmod +x unseed_larces_members.sh
#   ./unseed_larces_members.sh [BASE_URL] [ADMIN_EMAIL] [ADMIN_PASSWORD]
#
# Defaults:
#   BASE_URL       = http://localhost:5000
#   ADMIN_EMAIL    = admin@labhive.local
#   ADMIN_PASSWORD = changeme
#
# Requirements: curl, jq
# =============================================================================

set -euo pipefail

BASE_URL="${1:-http://localhost:5000}"
ADMIN_EMAIL="${2:-admin@labhive.local}"
ADMIN_PASSWORD="${3:-changeme}"
LAB_NAME="LARCES"

# ── colour helpers ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓ $*${NC}"; }
warn() { echo -e "${YELLOW}  ! $*${NC}"; }
err()  { echo -e "${RED}  ✗ $*${NC}"; }

# ── check dependencies ────────────────────────────────────────────────────────
for cmd in curl jq; do
  command -v "$cmd" &>/dev/null || { err "$cmd is required but not installed."; exit 1; }
done

# =============================================================================
# 1. Login as super-admin
# =============================================================================
echo "→ Logging in as $ADMIN_EMAIL …"
LOGIN=$(curl -sf -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}")

TOKEN=$(echo "$LOGIN" | jq -r '.access_token')
if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then
  err "Login failed. Check BASE_URL, ADMIN_EMAIL and ADMIN_PASSWORD."
  echo "$LOGIN"
  exit 1
fi
ok "Logged in. Token acquired."
AUTH=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")

# =============================================================================
# 2. Resolve LARCES lab id
# =============================================================================
echo "→ Looking up lab '$LAB_NAME' …"
LABS=$(curl -sf "$BASE_URL/labs/directory")
LAB_ID=$(echo "$LABS" | jq -r --arg name "$LAB_NAME" '.[] | select(.name == $name) | .id')

if [[ -z "$LAB_ID" || "$LAB_ID" == "null" ]]; then
  warn "Lab '$LAB_NAME' not found — nothing to clean up."
  exit 0
fi
ok "Found lab '$LAB_NAME' (id=$LAB_ID)."

# =============================================================================
# 3. CPFs of all members created by seed_larces_members.sh
# =============================================================================
declare -a SEED_CPFS=(
  "10000000002"   # Bruno Barbosa
  "10000000003"   # Carla Carvalho
  "10000000004"   # Diego Dias
  "10000000005"   # Elisa Ferreira
  "10000000006"   # Felipe Gomes
  "10000000007"   # Gabriela Henriques
  "10000000008"   # Henrique Ivo
  "10000000009"   # Isabela Jardim
  "10000000010"   # João Lopes
  "10000000011"   # Karina Melo
  "10000000012"   # Lucas Nunes
  "10000000013"   # Mariana Oliveira
  "10000000014"   # Nicolas Pinto
  "10000000015"   # Olivia Queiroz
  "10000000016"   # Pedro Rocha
  "10000000017"   # Rafaela Santos
  "10000000018"   # Samuel Teixeira
  "10000000019"   # Tatiana Uchoa
  "10000000020"   # Vitor Vieira
)

# =============================================================================
# 4. Remove each member from the lab and deactivate their account
# =============================================================================
REMOVED=0
SKIPPED=0

echo ""
echo "→ Removing members from lab $LAB_ID and deactivating accounts …"
echo ""

for CPF in "${SEED_CPFS[@]}"; do
  # ── 4a. Look up member by CPF ──────────────────────────────────────────────
  LOOKUP=$(curl -s "$BASE_URL/members/lookup?cpf=$CPF" "${AUTH[@]}")
  MEMBER_ID=$(echo "$LOOKUP" | jq -r '.id // empty')

  if [[ -z "$MEMBER_ID" ]]; then
    warn "CPF $CPF — member not found, skipping."
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  FULL_NAME=$(echo "$LOOKUP" | jq -r '"\(.first_name) \(.last_name)"')

  # ── 4b. Remove from lab (ignore 404 — may not be in this lab) ─────────────
  REMOVE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X DELETE "$BASE_URL/labs/$LAB_ID/members/$MEMBER_ID" \
    "${AUTH[@]}")

  if [[ "$REMOVE" == "204" ]]; then
    ok "$FULL_NAME (id=$MEMBER_ID) — removed from lab."
  elif [[ "$REMOVE" == "404" ]]; then
    warn "$FULL_NAME (id=$MEMBER_ID) — not in lab (already removed?)."
  else
    warn "$FULL_NAME (id=$MEMBER_ID) — lab removal returned HTTP $REMOVE."
  fi

  # ── 4c. Deactivate the account ─────────────────────────────────────────────
  DEACT=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "$BASE_URL/members/$MEMBER_ID/deactivate" \
    "${AUTH[@]}")

  if [[ "$DEACT" == "200" ]]; then
    ok "$FULL_NAME (id=$MEMBER_ID) — account deactivated."
    REMOVED=$((REMOVED + 1))
  else
    warn "$FULL_NAME (id=$MEMBER_ID) — deactivate returned HTTP $DEACT."
  fi
done

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "Done — $REMOVED deactivated, $SKIPPED not found."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

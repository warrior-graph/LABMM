#!/usr/bin/env bash
# =============================================================================
# seed_larces_members.sh
#
# Creates 19 members in the LARCES lab via the REST API.
# Each member's reports_to_id is set automatically at add-time:
#   engineering_manager / project_manager / chief_scientist → no manager
#   tech_lead   → first engineering_manager (or none)
#   everyone else → first tech_lead (or first manager, or none)
#
# Usage:
#   chmod +x seed_larces_members.sh
#   ./seed_larces_members.sh [BASE_URL] [ADMIN_EMAIL] [ADMIN_PASSWORD]
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
DEFAULT_PASSWORD="senha123"
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
  warn "Lab '$LAB_NAME' not found — creating it …"
  CREATE_LAB=$(curl -sf -X POST "$BASE_URL/labs" \
    "${AUTH[@]}" \
    -d "{\"name\":\"$LAB_NAME\",\"description\":\"Laboratório de Redes e Computação de Alto Desempenho\"}")
  LAB_ID=$(echo "$CREATE_LAB" | jq -r '.id')
  if [[ -z "$LAB_ID" || "$LAB_ID" == "null" ]]; then
    err "Failed to create lab '$LAB_NAME'."
    echo "$CREATE_LAB"
    exit 1
  fi
  ok "Lab '$LAB_NAME' created (id=$LAB_ID)."
else
  ok "Found lab '$LAB_NAME' (id=$LAB_ID)."
fi

# =============================================================================
# 3. Member data — 19 people with varied roles
#    Format: "FirstName|LastName|CPF|role1[,role2]"
#    CPFs are fake 11-digit numbers (not real).
#
#    Order matters: managers first, then leads, then contributors.
#    This ensures the superior id is known before the subordinate is added.
# =============================================================================
declare -a MEMBERS=(
  "Bruno|Barbosa|10000000002|engineering_manager"
  "Carla|Carvalho|10000000003|chief_scientist"
  "Diego|Dias|10000000004|project_manager"
  "Elisa|Ferreira|10000000005|engineering_manager"
  "Felipe|Gomes|10000000006|chief_scientist"
  "Gabriela|Henriques|10000000007|tech_lead"
  "Henrique|Ivo|10000000008|tech_lead,engineer"
  "Isabela|Jardim|10000000009|tech_lead"
  "João|Lopes|10000000010|engineer"
  "Karina|Melo|10000000011|engineer"
  "Lucas|Nunes|10000000012|engineer"
  "Mariana|Oliveira|10000000013|researcher"
  "Nicolas|Pinto|10000000014|researcher"
  "Olivia|Queiroz|10000000015|researcher,research_fellow"
  "Pedro|Rocha|10000000016|researcher"
  "Rafaela|Santos|10000000017|research_fellow"
  "Samuel|Teixeira|10000000018|research_fellow"
  "Tatiana|Uchoa|10000000019|research_fellow"
  "Vitor|Vieira|10000000020|staff"
)

# =============================================================================
# 4. Hierarchy tracking — filled as members are created
# =============================================================================
FIRST_MANAGER_ID=""  # first engineering_manager id (fallback for tech_leads)
FIRST_LEAD_ID=""     # first tech_lead id (fallback for contributors)

# Determine the appropriate reports_to_id for a given primary role
# Args: primary_role
reports_to_for_role() {
  local role="$1"
  case "$role" in
    engineering_manager|project_manager|chief_scientist)
      # Top-level managers — no superior in this seed
      echo ""
      ;;
    tech_lead)
      # Report to first engineering_manager (or none if not yet created)
      echo "${FIRST_MANAGER_ID:-}"
      ;;
    *)
      # engineer / researcher / research_fellow / staff
      # Report to first tech_lead, or first manager, or nobody
      echo "${FIRST_LEAD_ID:-${FIRST_MANAGER_ID:-}}"
      ;;
  esac
}

# =============================================================================
# 5. Register each member and add to the lab with reports_to_id
# =============================================================================
CREATED=0
SKIPPED=0

echo ""
echo "→ Creating members and adding to lab $LAB_ID …"
echo ""

for entry in "${MEMBERS[@]}"; do
  IFS='|' read -r FIRST LAST CPF ROLES_CSV <<< "$entry"
  EMAIL="${FIRST,,}.${LAST,,}@larces.local"

  # Primary role = first in the comma-separated list
  PRIMARY_ROLE="${ROLES_CSV%%,*}"

  # ── 5a. Register the member ────────────────────────────────────────────────
  REGISTER=$(curl -s -X POST "$BASE_URL/auth/register" \
    "${AUTH[@]}" \
    -d "{
      \"first_name\": \"$FIRST\",
      \"last_name\":  \"$LAST\",
      \"email\":      \"$EMAIL\",
      \"cpf\":        \"$CPF\",
      \"password\":   \"$DEFAULT_PASSWORD\"
    }")

  HTTP_ERR=$(echo "$REGISTER" | jq -r '.error // empty')
  if [[ -n "$HTTP_ERR" ]]; then
    warn "$FIRST $LAST ($EMAIL) — skipped: $HTTP_ERR"
    SKIPPED=$((SKIPPED + 1))
    # Try to resolve existing id so hierarchy tracking still works
    EXISTING_ID=$(curl -s "$BASE_URL/members/lookup?cpf=$CPF" \
      "${AUTH[@]}" | jq -r '.id // empty')
    MEMBER_ID="${EXISTING_ID:-}"
    [[ -z "$MEMBER_ID" ]] && continue
  else
    MEMBER_ID=$(echo "$REGISTER" | jq -r '.member.id')
    if [[ -z "$MEMBER_ID" || "$MEMBER_ID" == "null" ]]; then
      err "Unexpected response for $FIRST $LAST:"
      echo "$REGISTER"
      continue
    fi
  fi

  # ── 5b. Determine reports_to_id ────────────────────────────────────────────
  SUPERIOR_ID=$(reports_to_for_role "$PRIMARY_ROLE")

  # ── 5c. Build add-member payload ───────────────────────────────────────────
  ROLES_JSON=$(echo "$ROLES_CSV" | jq -Rc 'split(",")')

  if [[ -n "$SUPERIOR_ID" ]]; then
    PAYLOAD="{\"member_id\": $MEMBER_ID, \"roles\": $ROLES_JSON, \"reports_to_id\": $SUPERIOR_ID}"
  else
    PAYLOAD="{\"member_id\": $MEMBER_ID, \"roles\": $ROLES_JSON}"
  fi

  # ── 5d. Add member to the lab ──────────────────────────────────────────────
  ADD=$(curl -s -X POST "$BASE_URL/labs/$LAB_ID/members" \
    "${AUTH[@]}" \
    -d "$PAYLOAD")

  ADD_ERR=$(echo "$ADD" | jq -r '.error // empty')
  if [[ -n "$ADD_ERR" ]]; then
    warn "$FIRST $LAST — registered (id=$MEMBER_ID) but lab add failed: $ADD_ERR"
  else
    REPORTS_MSG=""
    [[ -n "$SUPERIOR_ID" ]] && REPORTS_MSG="  reports_to=$SUPERIOR_ID"
    ok "$FIRST $LAST <$EMAIL>  roles=[$ROLES_CSV]$REPORTS_MSG"
    CREATED=$((CREATED + 1))
  fi

  # ── 5e. Update hierarchy trackers ─────────────────────────────────────────
  case "$PRIMARY_ROLE" in
    engineering_manager)
      [[ -z "$FIRST_MANAGER_ID" ]] && FIRST_MANAGER_ID="$MEMBER_ID"
      ;;
    tech_lead)
      [[ -z "$FIRST_LEAD_ID" ]] && FIRST_LEAD_ID="$MEMBER_ID"
      ;;
  esac
done

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "Done — $CREATED created, $SKIPPED skipped."
echo "   Default password for all new members: $DEFAULT_PASSWORD"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

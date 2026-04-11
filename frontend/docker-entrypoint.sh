#!/bin/sh
set -e

# CASA-6: Input validation for environment variables
validate_url_or_path() {
  local value="$1"
  # Allow either:
  # 1. Full URLs: http://... or https://...
  # 2. Paths: starting with / containing only safe characters
  # 3. Special value: "auto" for dynamic detection
  if ! echo "$value" | grep -qE '^(https?://[a-zA-Z0-9][a-zA-Z0-9.-]*(:[0-9]+)?(/[a-zA-Z0-9/_-]*)?|/[a-zA-Z0-9/_-]*|auto)$'; then
    echo "ERROR: Invalid API_URL format: $value"
    echo "API_URL must be either a full URL (http://... or https://...), a path starting with /, or 'auto'"
    exit 1
  fi
}

validate_domain() {
  local domain="$1"
  # Basic domain validation (alphanumeric, dots, hyphens)
  if ! echo "$domain" | grep -qE '^[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]$'; then
    echo "ERROR: Invalid domain format: $domain"
    exit 1
  fi
}

validate_client_id() {
  local client_id="$1"
  # Basic alphanumeric validation
  if ! echo "$client_id" | grep -qE '^[a-zA-Z0-9_-]+$'; then
    echo "ERROR: Invalid client ID format"
    exit 1
  fi
}

validate_audience() {
  local audience="$1"
  # URL or URN validation
  if ! echo "$audience" | grep -qE '^(https?://|urn:)[a-zA-Z0-9:/.@_-]+$'; then
    echo "ERROR: Invalid audience format"
    exit 1
  fi
}

# Validate API_URL if provided (and not empty or auto)
if [ -n "$API_URL" ] && [ "$API_URL" != "auto" ]; then
  validate_url_or_path "$API_URL"
fi

# Validate Auth0 variables if provided
if [ -n "$AUTH0_DOMAIN" ]; then
  validate_domain "$AUTH0_DOMAIN"
fi

if [ -n "$AUTH0_CLIENT_ID" ]; then
  validate_client_id "$AUTH0_CLIENT_ID"
fi

if [ -n "$AUTH0_AUDIENCE" ]; then
  validate_audience "$AUTH0_AUDIENCE"
fi

if [ -n "$VITE_CONNECT_URL" ]; then
  validate_url_or_path "$VITE_CONNECT_URL"
fi

# Determine if auth should be enabled
# Priority: 1. ENABLE_AUTH env var 2. If Auth0 vars present 3. Default off
if [ "${ENABLE_AUTH}" = "true" ]; then
  AUTH_ENABLED=true
elif [ -n "$AUTH0_DOMAIN" ] && [ -n "$AUTH0_CLIENT_ID" ] && [ -n "$AUTH0_AUDIENCE" ]; then
  AUTH_ENABLED=true
  echo "Auth enabled because Auth0 credentials are provided"
else
  AUTH_ENABLED=false
  echo "Auth disabled (no credentials or ENABLE_AUTH not set to true)"
fi

# Create config.js with runtime environment variables
# Handle 'auto' value for dynamic IP detection
if [ "$API_URL" = "auto" ] || [ -z "$API_URL" ]; then
  echo "Generating runtime config with API_URL=auto (dynamic detection enabled)"
  cat > /app/dist/config.js << EOF
window.ENV = {
  API_URL: "auto",
  AUTH_ENABLED: ${AUTH_ENABLED},
  AUTH0_DOMAIN: "${AUTH0_DOMAIN:-}",
  AUTH0_CLIENT_ID: "${AUTH0_CLIENT_ID:-}",
  AUTH0_AUDIENCE: "${AUTH0_AUDIENCE:-}"
};
console.log("Runtime config loaded:", window.ENV);
console.log("Dynamic IP detection enabled - API will be auto-configured");
EOF
  echo "Runtime config injected successfully. API_URL set to: auto"
else
  echo "Generating runtime config with API_URL=${API_URL}"
  cat > /app/dist/config.js << EOF
window.ENV = {
  API_URL: "${API_URL}",
  AUTH_ENABLED: ${AUTH_ENABLED},
  AUTH0_DOMAIN: "${AUTH0_DOMAIN:-}",
  AUTH0_CLIENT_ID: "${AUTH0_CLIENT_ID:-}",
  AUTH0_AUDIENCE: "${AUTH0_AUDIENCE:-}"
};
console.log("Runtime config loaded:", window.ENV);
EOF
  echo "Runtime config injected successfully. API_URL set to: ${API_URL}"
fi

# Make sure config.js is loaded before any other scripts
# First, backup original index.html
cp /app/dist/index.html /app/dist/index.html.bak

# Insert config.js in <head> section to ensure it loads first
sed -i 's|</head>|  <script src="/config.js"></script>\n  </head>|' /app/dist/index.html

# Substitute environment variables into serve.json CSP and copy to dist
if [ -f /app/serve.json ]; then
  if [ -n "$API_URL" ] && [ "$API_URL" != "auto" ]; then
    sed -i "s|__API_URL__|${API_URL}|g" /app/serve.json
  else
    sed -i "s|__API_URL__||g" /app/serve.json
  fi
  if [ -n "$AUTH0_DOMAIN" ]; then
    sed -i "s|__AUTH0_DOMAIN__|https://${AUTH0_DOMAIN}|g" /app/serve.json
  else
    sed -i "s|__AUTH0_DOMAIN__||g" /app/serve.json
  fi
  if [ -n "$VITE_CONNECT_URL" ]; then
    sed -i "s|__CONNECT_URL__|${VITE_CONNECT_URL}|g" /app/serve.json
  else
    sed -i "s|__CONNECT_URL__||g" /app/serve.json
  fi
  cp /app/serve.json /app/dist/serve.json
  echo "Security headers configuration loaded"
fi

# Run command with serve.json configuration
exec serve -s /app/dist -l 8080 --no-clipboard --no-port-switching
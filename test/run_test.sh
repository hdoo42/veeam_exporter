#!/bin/bash
# Token refresh test script

set -e

echo "=========================================="
echo "Veeam Token Refresh Logic Test"
echo "=========================================="
echo ""

# Check if httpapi_exporter exists
if [ ! -f "./httpapi_exporter" ]; then
    echo "ERROR: httpapi_exporter binary not found in current directory"
    echo "Please download it first:"
    echo "  wget https://github.com/ksy4228/httpapi_exporter/releases/download/v0.4.2/httpapi_exporter-linux-amd64"
    echo "  chmod +x httpapi_exporter"
    exit 1
fi

echo "Step 1: Starting mock Veeam server..."
python3 test/mock_veeam_server.py &
MOCK_PID=$!
sleep 2

echo ""
echo "Step 2: Running initial test (should login with password)..."
./httpapi_exporter -c test/test_config.yml -n -t localhost || true

echo ""
echo "Step 3: Waiting 30 seconds (token expires in 60s, should refresh at 55s)..."
echo "    Current time: $(date '+%H:%M:%S')"
echo "    Token issued at: $(date '+%H:%M:%S')"
echo "    Should refresh around: $(date -v+55S '+%H:%M:%S' 2>/dev/null || date -d '+55 seconds' '+%H:%M:%S')"
echo ""

for i in {30..1}; do
    echo -ne "\r    Countdown: $i seconds remaining..."
    sleep 1
done
echo ""
echo ""

echo "Step 4: Running test after 30 seconds (should use existing token)..."
./httpapi_exporter -c test/test_config.yml -n -t localhost || true

echo ""
echo "Step 5: Waiting another 35 seconds (token should expire, forcing refresh)..."
for i in {35..1}; do
    echo -ne "\r    Countdown: $i seconds remaining..."
    sleep 1
done
echo ""
echo ""

echo "Step 6: Running test after token expiry (should refresh with refresh_token)..."
./httpapi_exporter -c test/test_config.yml -n -t localhost || true

echo ""
echo "=========================================="
echo "Test completed!"
echo "=========================================="
echo ""
echo "Check the mock server output above:"
echo "  - 'Grant type: password' = Initial login"
echo "  - 'Grant type: refresh_token' = Token refreshed"
echo ""

# Cleanup
echo "Cleaning up mock server..."
kill $MOCK_PID 2>/dev/null || true

echo "Done!"

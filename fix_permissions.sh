#!/bin/bash
# Diagnostic and permission fix script for edge-video-agent

echo "=== Edge Video Agent - Permission Diagnostic & Fix ==="
echo ""

# Get current user
CURRENT_USER=$(whoami)
echo "Current user: $CURRENT_USER"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "⚠️  Running as root/sudo"
    echo ""
fi

# Check config.yaml
echo "Checking config.yaml..."
if [ -f config.yaml ]; then
    ls -la config.yaml
    if [ ! -w config.yaml ]; then
        echo "❌ config.yaml is NOT writable"
        echo "Fixing permissions..."
        chmod 644 config.yaml
        chown $CURRENT_USER:$CURRENT_USER config.yaml 2>/dev/null || chown $CURRENT_USER config.yaml
        echo "✓ Fixed"
    else
        echo "✓ config.yaml is writable"
    fi
else
    echo "❌ config.yaml not found"
fi
echo ""

# Check logs directory
echo "Checking logs/ directory..."
if [ -d logs ]; then
    ls -la logs/
    if [ ! -w logs ]; then
        echo "❌ logs/ is NOT writable"
        echo "Fixing permissions..."
        chmod -R 755 logs/
        chown -R $CURRENT_USER:$CURRENT_USER logs/ 2>/dev/null || chown -R $CURRENT_USER logs/
        echo "✓ Fixed"
    else
        echo "✓ logs/ is writable"
    fi

    # Fix individual log files
    echo "Fixing log file permissions..."
    find logs/ -type f -exec chmod 644 {} \;
    find logs/ -type f -exec chown $CURRENT_USER:$CURRENT_USER {} \; 2>/dev/null || find logs/ -type f -exec chown $CURRENT_USER {} \;
    echo "✓ All log files fixed"
else
    echo "Creating logs/ directory..."
    mkdir -p logs
    chmod 755 logs
    echo "✓ Created"
fi
echo ""

# Check tmp/chunks directory
echo "Checking tmp/chunks/ directory..."
if [ -d tmp/chunks ]; then
    ls -la tmp/chunks/ | head -n 20
    if [ ! -w tmp/chunks ]; then
        echo "❌ tmp/chunks/ is NOT writable"
        echo "Fixing permissions..."
        chmod -R 755 tmp/chunks/
        chown -R $CURRENT_USER:$CURRENT_USER tmp/chunks/ 2>/dev/null || chown -R $CURRENT_USER tmp/chunks/
        echo "✓ Fixed"
    else
        echo "✓ tmp/chunks/ is writable"
    fi

    # Fix individual chunk files
    echo "Fixing chunk file permissions..."
    find tmp/chunks/ -type f -exec chmod 644 {} \;
    find tmp/chunks/ -type f -exec chown $CURRENT_USER:$CURRENT_USER {} \; 2>/dev/null || find tmp/chunks/ -type f -exec chown $CURRENT_USER {} \;
    echo "✓ All chunk files fixed"
else
    echo "Creating tmp/chunks/ directory..."
    mkdir -p tmp/chunks
    chmod 755 tmp/chunks
    echo "✓ Created"
fi
echo ""

echo "=== Permission Check Complete ==="
echo ""
echo "Next steps:"
echo "1. Restart the Flask app: sudo systemctl restart edge-video-agent (if using systemd)"
echo "   OR: Kill and restart: pkill -f app.py && python app.py"
echo "2. Try changing the camera ID again"
echo ""

#!/bin/bash
# Quick test script to run decoder diagnostics with proper URL quoting

echo "========================================================================"
echo "  Testing Hardware Decoder with RTSP URLs"
echo "========================================================================"
echo ""

# RTSP URLs from config.yaml
RTSP_URL_1="rtsp://admin:tapway123@192.168.0.14:554/cam/realmonitor?channel=1&subtype=0"
RTSP_URL_2="rtsp://admin:tapway123@192.168.0.130:554/cam/realmonitor?channel=1&subtype=0"
RTSP_URL_3="rtsp://admin:tapway123@192.168.0.198:554/cam/realmonitor?channel=1&subtype=0"

echo "Choose which test to run:"
echo "1) Quick diagnosis (diagnose_decoder.py)"
echo "2) Detailed troubleshooting (troubleshoot_rtsp_decoder.py)"
echo "3) Test all cameras"
echo ""
read -p "Enter choice [1-3]: " choice

case $choice in
    1)
        echo ""
        echo "Running diagnose_decoder.py with camera 192.168.0.130..."
        python diagnose_decoder.py "$RTSP_URL_2"
        ;;
    2)
        echo ""
        echo "Select camera:"
        echo "1) 192.168.0.14 (Pantry)"
        echo "2) 192.168.0.130 (Office Window)"
        echo "3) 192.168.0.198 (Office Entrance)"
        read -p "Enter camera [1-3]: " cam
        
        case $cam in
            1)
                echo ""
                echo "Testing camera 192.168.0.14..."
                python troubleshoot_rtsp_decoder.py "$RTSP_URL_1"
                ;;
            2)
                echo ""
                echo "Testing camera 192.168.0.130..."
                python troubleshoot_rtsp_decoder.py "$RTSP_URL_2"
                ;;
            3)
                echo ""
                echo "Testing camera 192.168.0.198..."
                python troubleshoot_rtsp_decoder.py "$RTSP_URL_3"
                ;;
            *)
                echo "Invalid choice"
                exit 1
                ;;
        esac
        ;;
    3)
        echo ""
        echo "Testing all cameras (quick test)..."
        echo ""
        
        echo "========================================================================"
        echo "Camera 1: 192.168.0.14 (Pantry)"
        echo "========================================================================"
        python troubleshoot_rtsp_decoder.py "$RTSP_URL_1"
        
        echo ""
        echo "========================================================================"
        echo "Camera 2: 192.168.0.130 (Office Window)"
        echo "========================================================================"
        python troubleshoot_rtsp_decoder.py "$RTSP_URL_2"
        
        echo ""
        echo "========================================================================"
        echo "Camera 3: 192.168.0.198 (Office Entrance)"
        echo "========================================================================"
        python troubleshoot_rtsp_decoder.py "$RTSP_URL_3"
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "========================================================================"
echo "Test complete!"
echo "========================================================================"

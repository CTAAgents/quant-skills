#!/usr/bin/env python3
"""
PolyMarket router client - calls the router system
"""

import sys
import json
import os
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

try:
    from polymarket_router import SmartRouter, DataRequest, DataResponse
    from polymarket_router.source_manager import SourceManager
except ImportError as e:
    print(json.dumps({
        "error": f"Failed to import router modules: {str(e)}",
        "success": False
    }))
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "No request provided",
            "success": False
        }))
        sys.exit(1)

    try:
        request_json = sys.argv[1]
        request_data = json.loads(request_json)
        
        # Create source manager and router
        source_manager = SourceManager()
        router = SmartRouter(source_manager)
        
        # Create request object
        request = DataRequest(
            query=request_data.get('query', ''),
            data_type=request_data.get('type', 'market_data'),
            timeout=request_data.get('timeout', 10000)
        )
        
        # Execute request
        response = router.execute_request_sync(request)
        
        # Convert response to dictionary
        result = {
            "success": True,
            "data": response.data if response else None,
            "source": response.source if response else "unknown",
            "quality": response.quality_score if response else 0,
            "timestamp": response.timestamp.isoformat() if response and response.timestamp else None,
            "metadata": response.metadata if response else {}
        }
        
        print(json.dumps(result))
        
    except json.JSONDecodeError as e:
        print(json.dumps({
            "error": f"Invalid JSON request: {str(e)}",
            "success": False
        }))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({
            "error": f"Router execution failed: {str(e)}",
            "success": False
        }))
        sys.exit(1)

if __name__ == "__main__":
    main()
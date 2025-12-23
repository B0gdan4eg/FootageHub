#!/usr/bin/env python3
"""
Convert exported cookies to Playwright JSON format for Motion Array.

Usage:
    python motion_utils/convert_cookies.py input.json [number]
    
Examples:
    python motion_utils/convert_cookies.py exported.json
    python motion_utils/convert_cookies.py exported.json 1
"""

import json
import sys
from pathlib import Path


def convert_cookies_to_playwright(input_file: str, number: int = None):
    """Convert various cookie formats to Playwright JSON format"""
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Try to parse as JSON first
    try:
        cookies = json.loads(content)
        
        # If it's already a list of cookies, validate format
        if isinstance(cookies, list):
            playwright_cookies = []
            for cookie in cookies:
                # Convert to Playwright format if needed
                pw_cookie = {
                    'name': cookie.get('name'),
                    'value': cookie.get('value'),
                    'domain': cookie.get('domain', '.motionarray.com'),
                    'path': cookie.get('path', '/'),
                }
                
                # Optional fields
                if 'expires' in cookie:
                    pw_cookie['expires'] = cookie['expires']
                if 'httpOnly' in cookie:
                    pw_cookie['httpOnly'] = cookie['httpOnly']
                if 'secure' in cookie:
                    pw_cookie['secure'] = cookie['secure']
                # sameSite: только если есть и не null (Playwright требует Strict|Lax|None)
                if 'sameSite' in cookie and cookie['sameSite'] in ['Strict', 'Lax', 'None']:
                    pw_cookie['sameSite'] = cookie['sameSite']
                    
                playwright_cookies.append(pw_cookie)
            
            # Determine output paths
            if number:
                service_output = f"motion_utils/motion_cookies_{number}.json"
                test_output = f"test/motion_cookies_{number}.json"
            else:
                service_output = "motion_utils/motion_cookies.json"
                test_output = "test/motion_cookies.json"
            
            # Create directories
            Path("motion_utils").mkdir(parents=True, exist_ok=True)
            Path("test").mkdir(parents=True, exist_ok=True)
            
            # Save in both locations
            with open(service_output, 'w', encoding='utf-8') as f:
                json.dump(playwright_cookies, f, indent=2, ensure_ascii=False)
            
            with open(test_output, 'w', encoding='utf-8') as f:
                json.dump(playwright_cookies, f, indent=2, ensure_ascii=False)
            
            print(f"[SUCCESS] Converted {len(playwright_cookies)} cookies")
            print(f"[FILES]:")
            print(f"   - {service_output}")
            print(f"   - {test_output}")
            return
            
    except json.JSONDecodeError:
        # Not JSON, might be Netscape format
        pass
    
    # Try Netscape format
    lines = content.strip().split('\n')
    playwright_cookies = []
    
    for line in lines:
        if line.startswith('#') or not line.strip():
            continue
            
        parts = line.split('\t')
        if len(parts) >= 7:
            cookie = {
                'name': parts[5],
                'value': parts[6],
                'domain': parts[0],
                'path': parts[2],
                'expires': int(parts[4]) if parts[4] != '0' else -1,
                'httpOnly': parts[1] == 'TRUE',
                'secure': parts[3] == 'TRUE',
            }
            playwright_cookies.append(cookie)
    
    if playwright_cookies:
        # Determine output paths
        if number:
            service_output = f"motion_utils/motion_cookies_{number}.json"
            test_output = f"test/motion_cookies_{number}.json"
        else:
            service_output = "motion_utils/motion_cookies.json"
            test_output = "test/motion_cookies.json"
        
        # Create directories
        Path("motion_utils").mkdir(parents=True, exist_ok=True)
        Path("test").mkdir(parents=True, exist_ok=True)
        
        # Save in both locations
        with open(service_output, 'w', encoding='utf-8') as f:
            json.dump(playwright_cookies, f, indent=2, ensure_ascii=False)
        
        with open(test_output, 'w', encoding='utf-8') as f:
            json.dump(playwright_cookies, f, indent=2, ensure_ascii=False)
        
        print(f"[SUCCESS] Converted {len(playwright_cookies)} cookies from Netscape format")
        print(f"[FILES]:")
        print(f"   - {service_output}")
        print(f"   - {test_output}")
        return
    
    print("[ERROR] Failed to parse cookies. Unsupported format.")
    sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python motion_utils/convert_cookies.py <input_file> [number]")
        print("\nExamples:")
        print("  python motion_utils/convert_cookies.py exported_cookies.json")
        print("  python motion_utils/convert_cookies.py exported_cookies.json 1")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if not Path(input_file).exists():
        print(f"[ERROR] Input file not found: {input_file}")
        sys.exit(1)
    
    # Parse optional number argument
    number = None
    if len(sys.argv) >= 3:
        try:
            number = int(sys.argv[2])
        except ValueError:
            print(f"[ERROR] Invalid number: {sys.argv[2]}")
            sys.exit(1)
    
    convert_cookies_to_playwright(input_file, number)


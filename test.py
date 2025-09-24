import subprocess
import json
import os

def convert_html_to_markdown(html_content, enable_table_plugin=True):
    """Convert HTML to markdown using the html2markdown CLI"""
    try:
        # Use the correct path to the executable in the html-to-markdown directory
        executable_path = './html-to-markdown/html2markdown.exe'
        
        # Check if the executable exists
        if not os.path.exists(executable_path):
            print(f"Executable not found at {executable_path}")
            return None
        
        # Build command with table plugin if requested
        cmd = [executable_path]
        if enable_table_plugin:
            cmd.append('--plugin-table')
        
        # Run the CLI tool with HTML content as stdin
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(input=html_content)
        
        if process.returncode == 0:
            return stdout.strip()
        else:
            print(f"Error converting HTML: {stderr}")
            return None
            
    except Exception as e:
        print(f"Error running html2markdown: {e}")
        return None

# Usage example with table
html_content = "<table><tr><td>ID</td><td>Description</td></tr><tr><td>02434953</td><td>Extreme AirDefense Essentials might generate false rogue AP alarms</td></tr><tr><td>02590366</td><td>due to incorrectly identifying neighboring Extreme Networks AP</td></tr><tr><td>02666601</td><td>devices using the same network policy as rogue APs.</td></tr></table>"

markdown_result = convert_html_to_markdown(html_content, enable_table_plugin=True)
if markdown_result:
    print(f"Converted markdown:\n{markdown_result}")
else:
    print("Conversion failed")
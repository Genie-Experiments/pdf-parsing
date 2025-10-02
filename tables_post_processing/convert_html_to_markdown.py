import subprocess
import os
import platform
import stat
from pathlib import Path


class HTMLToMarkdownConverter:
    """Cross-platform HTML to Markdown converter using pre-compiled html2markdown binaries"""
    
    def __init__(self):
        self.platform = platform.system()
        self.is_colab = self._detect_colab()
        self.html_to_markdown_dir = self._find_html_to_markdown_dir()
        self.executable_path = self._get_executable_path()
    
    def _detect_colab(self):
        """Detect if running in Google Colab"""
        try:
            import google.colab
            return True
        except ImportError:
            return False
    
    def _find_html_to_markdown_dir(self):
        """Find the html-to-markdown directory in various possible locations"""
        possible_locations = [
            Path('./html-to-markdown'),
            Path('../html-to-markdown'),
            Path.cwd() / 'html-to-markdown',
            Path('/content/pdf-parsing-pipeline/html-to-markdown'),
            Path('/content/html-to-markdown'),
        ]
        
        for location in possible_locations:
            if location.exists() and location.is_dir():
                return location
        
        # Fallback to default
        return Path('./html-to-markdown')
    
    def _get_executable_path(self):
        """Get the correct pre-compiled binary path based on the operating system"""
        bin_dir = self.html_to_markdown_dir / 'bin'
        
        if self.platform == 'Windows':
            # Windows executable
            return bin_dir / 'html2markdown.exe'
        
        elif self.platform == 'Darwin':  # macOS
            # Check for Apple Silicon first, fallback to Intel
            if platform.machine() == 'arm64':
                return bin_dir / 'html-to-markdown_Darwin_arm64'
            else:
                # For Intel Macs or unknown architecture, try arm64 binary (often compatible)
                return bin_dir / 'html-to-markdown_Darwin_arm64'
        
        else:  # Linux (including Google Colab)
            return bin_dir / 'html-to-markdown_Linux_x86_64'
    
    def _ensure_executable_permissions(self):
        """Ensure the binary has execute permissions on Unix systems"""
        if self.platform == 'Windows':
            return True  # Windows doesn't need execute permissions
        
        try:
            # Check if file has execute permissions
            if not os.access(self.executable_path, os.X_OK):
                # Add execute permissions
                current_permissions = self.executable_path.stat().st_mode
                new_permissions = current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
                self.executable_path.chmod(new_permissions)
            
            return True
        except Exception as e:
            print(f"Warning: Could not set executable permissions: {e}")
            return False
    
    def _validate_setup(self):
        """Validate that the binary exists and is functional"""
        # Check if html-to-markdown directory exists
        if not self.html_to_markdown_dir.exists():
            print(f"✗ html-to-markdown directory not found")
            return False
        
        # Check if bin directory exists
        bin_dir = self.html_to_markdown_dir / 'bin'
        if not bin_dir.exists():
            print(f"✗ bin directory not found at {bin_dir}")
            print("  Please ensure the pre-compiled binaries are in the bin folder")
            return False
        
        # Check if the specific binary exists
        if not self.executable_path.exists():
            print(f"✗ Binary not found at {self.executable_path}")
            print(f"  Platform: {self.platform}")
            print(f"  Available files in bin/:")
            try:
                for file in bin_dir.iterdir():
                    print(f"    - {file.name}")
            except:
                print("    (could not list files)")
            return False
        
        # Ensure executable permissions on Unix systems
        if not self._ensure_executable_permissions():
            return False
        
        # Test the binary with a simple conversion
        return self._test_binary()
    
    def _test_binary(self):
        """Test the binary with a simple HTML conversion"""
        try:
            test_html = "<p>test</p>"
            process = subprocess.run(
                [str(self.executable_path)],
                input=test_html,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if process.returncode == 0 and "test" in process.stdout:
                return True
            else:
                print(f"✗ Binary test failed:")
                print(f"  Return code: {process.returncode}")
                print(f"  stdout: {process.stdout}")
                print(f"  stderr: {process.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("✗ Binary test timed out")
            return False
        except Exception as e:
            print(f"✗ Binary test failed: {e}")
            return False
    
    def convert(self, html_content, enable_table_plugin=True, verbose=True):
        """Convert HTML to markdown using the pre-compiled binary
        
        Args:
            html_content (str): HTML content to convert
            enable_table_plugin (bool): Whether to enable table plugin
            verbose (bool): Whether to print status messages
            
        Returns:
            str: Converted markdown content, or None if conversion failed
        """
        if verbose:
            env_type = "Google Colab" if self.is_colab else self.platform
            print(f"Converting HTML to Markdown on {env_type}...")
        
        # Validate setup
        if not self._validate_setup():
            if verbose:
                print("✗ Setup validation failed")
            return None
        
        try:
            # Build command
            cmd = [str(self.executable_path)]
            if enable_table_plugin:
                cmd.append('--plugin-table')
            
            if verbose:
                print(f"Running: {self.executable_path.name} {'--plugin-table' if enable_table_plugin else ''}")
            
            # Run the conversion
            process = subprocess.run(
                cmd,
                input=html_content,
                capture_output=True,
                text=True,
            )
            
            if process.returncode == 0:
                if verbose:
                    print("✓ HTML to Markdown conversion successful")
                return process.stdout.strip()
            else:
                if verbose:
                    print(f"✗ Conversion failed (exit code {process.returncode})")
                    print(f"Error: {process.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            if verbose:
                print("✗ Conversion timed out after 30 seconds")
            return None
        except Exception as e:
            if verbose:
                print(f"✗ Error during conversion: {e}")
            return None
    
    def get_info(self):
        """Get information about the current setup"""
        info = {
            'platform': self.platform,
            'is_colab': self.is_colab,
            'html_to_markdown_dir': str(self.html_to_markdown_dir),
            'executable_path': str(self.executable_path),
            'executable_exists': self.executable_path.exists(),
            'directory_exists': self.html_to_markdown_dir.exists(),
        }
        
        # Check if binary is executable on Unix systems
        if self.platform != 'Windows' and self.executable_path.exists():
            info['is_executable'] = os.access(self.executable_path, os.X_OK)
        
        return info


def convert_html_to_markdown(html_content, enable_table_plugin=True, verbose=False):
    """Convert HTML to markdown using pre-compiled html2markdown binaries
    
    Simple interface function for HTML to Markdown conversion.
    
    Args:
        html_content (str): HTML content to convert
        enable_table_plugin (bool): Whether to enable table plugin for better table handling
        verbose (bool): Whether to print detailed status messages
        
    Returns:
        str: Converted markdown content, or None if conversion failed
    """
    converter = HTMLToMarkdownConverter()
    return converter.convert(html_content, enable_table_plugin, verbose)


def get_converter_info():
    """Get information about the current converter setup"""
    converter = HTMLToMarkdownConverter()
    return converter.get_info()

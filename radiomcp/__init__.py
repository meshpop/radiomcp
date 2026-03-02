"""
radiomcp - MCP server for internet radio

24,000+ stations from 197 countries
Song recognition, AI recommendations, multilingual search
"""

__version__ = "1.0.0"
__author__ = "dragonflydiy"

from .server import main, mcp

__all__ = ["main", "mcp", "__version__"]

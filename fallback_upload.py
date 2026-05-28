#!/usr/bin/env python3
"""Fallback upload wrapper for the workflow step."""
import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.execvp(sys.executable, [sys.executable, 'recorder.py', 'fallback'])

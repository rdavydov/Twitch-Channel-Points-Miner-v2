#!/bin/bash
echo cleaning __pycache__
find . -name "__pycache__" -exec rm -rf {} \; 2>/dev/null
echo Done!

#!/bin/bash
cd /Users/denny/kicksy-agent/kicksy-agent
source venv/bin/activate
exec caffeinate -i python main.py

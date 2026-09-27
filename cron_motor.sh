#!/bin/bash
cd ~/ARCTURUS_CLIMATIK
termux-wake-lock
python3 arcturus.py >> logs/cron_motor.log 2>&1

#!/bin/bash
source /home/ubuntu/marketbot/sendgrid.env
source /home/ubuntu/marketbot/venv/bin/activate
python /home/ubunut/marketbot/webhook_listener.py &
python /home/ubuntu/marketbot/bot_worker.py & 
echo "`ps aux |grep py`" 

ssh -i "./botx.pem" ubuntu@ec2-52-34-35-240.us-west-2.compute.amazonaws.com << EOF
cd ~/marketbot && git pull origin master && source venv/bin/activate && pip install -r requirements.txt && echo "`whoami`" && scripts/restart.sh && echo '[OK]'
EOF

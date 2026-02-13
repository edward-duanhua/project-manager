#!/usr/bin/env python3
"""
Send email via SMTP (if configured) or local mail/sendmail.
Usage: send_email.py --to <recipient> --subject <subject> --body <body> [--cc <cc>] [--smtp-server <host>] [--smtp-port <port>] [--smtp-user <user>] [--smtp-pass <pass>]
"""
import sys
import argparse
import subprocess
import shutil
import smtplib
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Define path to config file relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "../data/config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"WARNING: Invalid JSON in {CONFIG_FILE}")
    return {}


def send_email_smtp(to, subject, body, cc=None, smtp_config=None):
    if not smtp_config:
        return False
        
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_config.get('user')
        msg['To'] = to
        msg['Subject'] = subject
        if cc:
            msg['Cc'] = cc
            
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(smtp_config.get('server'), int(smtp_config.get('port', 587)))
        server.starttls()
        server.login(smtp_config.get('user'), smtp_config.get('password'))
        
        recipients = [to]
        if cc:
            recipients.append(cc)
            
        server.sendmail(smtp_config.get('user'), recipients, msg.as_string())
        server.quit()
        print(f"SUCCESS: Email sent to {to} via SMTP ({smtp_config.get('server')})")
        return True
    except Exception as e:
        print(f"ERROR: SMTP failed: {e}")
        return False

def send_email_local(to, subject, body, cc=None):
    # Try to find a mail command
    mail_cmd = shutil.which('mail') or shutil.which('mailx')
    
    if mail_cmd:
        try:
            cmd = [mail_cmd, '-s', subject, to]
            if cc:
                cmd.extend(['-c', cc])
                
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate(input=body)
            
            if process.returncode == 0:
                print(f"SUCCESS: Email sent to {to} via {mail_cmd}")
                return True
            else:
                print(f"ERROR: Failed to send via {mail_cmd}. {stderr}")
        except Exception as e:
            print(f"ERROR: Exception while sending email: {e}")
    return False

def log_email(to, subject, body, cc=None):
    # Fallback: Just log it to a file "sent_emails.log" in workspace
    try:
        log_file = "sent_emails.log"
        with open(log_file, "a") as f:
            f.write(f"--- EMAIL ---\nTo: {to}\nCc: {cc}\nSubject: {subject}\nBody:\n{body}\n----------------\n\n")
        print(f"SIMULATED: Email appended to {log_file} (No mail server configured)")
        return True
    except Exception as e:
        print(f"ERROR: Failed to log email: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send an email.")
    parser.add_argument("--to", required=True, help="Recipient email")
    parser.add_argument("--subject", required=True, help="Email subject")
    parser.add_argument("--body", required=True, help="Email body")
    parser.add_argument("--cc", help="CC recipient")
    
    # SMTP arguments
    parser.add_argument("--smtp-server", help="SMTP Server Host")
    parser.add_argument("--smtp-port", default=587, help="SMTP Server Port")
    parser.add_argument("--smtp-user", help="SMTP Username")
    parser.add_argument("--smtp-pass", help="SMTP Password")
    
    args = parser.parse_args()
    
    # Check for SMTP env vars if not provided
    smtp_server = args.smtp_server or os.environ.get('SMTP_SERVER')
    smtp_port = args.smtp_port or os.environ.get('SMTP_PORT')
    smtp_user = args.smtp_user or os.environ.get('SMTP_USER')
    smtp_pass = args.smtp_pass or os.environ.get('SMTP_PASS')
    
    # Check config file if still missing
    if not (smtp_server and smtp_user and smtp_pass):
        config = load_config()
        smtp_cfg = config.get('smtp', {})
        if not smtp_server: smtp_server = smtp_cfg.get('server')
        if not smtp_port: smtp_port = smtp_cfg.get('port')
        if not smtp_user: smtp_user = smtp_cfg.get('user')
        if not smtp_pass: smtp_pass = smtp_cfg.get('password')

    # Default port if not set anywhere
    if not smtp_port:
        smtp_port = 587
    
    smtp_config = None
    if smtp_server and smtp_user and smtp_pass:
        smtp_config = {
            "server": smtp_server,
            "port": smtp_port,
            "user": smtp_user,
            "password": smtp_pass
        }

    # Strategy: SMTP -> Local Command -> Log File
    if smtp_config and send_email_smtp(args.to, args.subject, args.body, args.cc, smtp_config):
        sys.exit(0)
        
    if send_email_local(args.to, args.subject, args.body, args.cc):
        sys.exit(0)
        
    log_email(args.to, args.subject, args.body, args.cc)

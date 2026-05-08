import os
import smtplib
from datetime import datetime
from email.message import EmailMessage


def send_stop_email(sensor_data, verdict):
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    sender = os.environ.get("ALERT_SENDER")
    recipient = os.environ.get("ALERT_RECIPIENT")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))

    if not all([smtp_host, smtp_user, smtp_pass, sender, recipient]):
        print("Email skipped: SMTP configuration incomplete")
        return

    msg = EmailMessage()
    msg["Subject"] = f"Machine STOPPED: {sensor_data['machine_id']}"
    msg["From"] = sender
    msg["To"] = recipient

    body = f"""
Machine Stoppage Alert

Machine ID: {sensor_data['machine_id']}
Timestamp: {datetime.utcnow().isoformat()}

--- Sensor Data ---
Temperature: {sensor_data['temperature']}
Vibration: {sensor_data['vibration']}
Current: {sensor_data['current']}
Switch State: {sensor_data.get('switch_state', 'Off')}

--- AI Verdict ---
Health Score: {verdict.get('health_score', 'N/A')}
Health Status: {verdict.get('health_status', 'N/A')}
Issues: {', '.join(verdict.get('issues', []))}
Stopping Required: {verdict['stopping_required']}
Anomaly Probability: {verdict.get('anomaly_prob', 'N/A')}
Normal Score: {verdict.get('normal_score', 'N/A')}

Action Taken: STOP SIGNAL ISSUED
"""

    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        print("Email sent successfully")
    except Exception as e:
        print("Email failed:", e)

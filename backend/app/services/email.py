import logging,smtplib
from email.message import EmailMessage
from ..config import settings
logger=logging.getLogger("civiclens.email")
def send_email(to:str,subject:str,body:str):
    if not settings.smtp_host:
        if not settings.is_production:logger.info("DEV EMAIL to=%s subject=%s body=%s",to,subject,body)
        return
    message=EmailMessage();message["From"]=settings.smtp_from_email;message["To"]=to;message["Subject"]=subject;message.set_content(body)
    with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=15) as smtp:
        if settings.smtp_use_tls:smtp.starttls()
        if settings.smtp_username:smtp.login(settings.smtp_username,settings.smtp_password or "")
        smtp.send_message(message)
def send_verification(to:str,token:str):send_email(to,"Verify your CivicLens email",f"Verify your email: {settings.app_base_url}/verify-email?token={token}\n\nThis link expires in 24 hours.")
def send_password_reset(to:str,token:str):send_email(to,"Reset your CivicLens password",f"Reset your password: {settings.app_base_url}/reset-password?token={token}\n\nThis link expires in 30 minutes.")
def send_status_update(to:str,reference:str,title:str,status:str,note:str,complaint_id:str):send_email(to,f"{reference} is now {status.replace('_',' ')}",f"{title}\n\nStatus: {status.replace('_',' ').title()}\n{note}\n\nTrack this complaint: {settings.app_base_url}/complaints/{complaint_id}")

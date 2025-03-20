from django.db import models
from django.utils import timezone
import uuid
import json

class ServiceM8Credentials(models.Model):
    company_uuid = models.CharField(max_length=36, unique=True)
    access_token = models.CharField(max_length=255)
    refresh_token = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    
    def is_expired(self):
        return timezone.now() >= self.expires_at
    
    def __str__(self):
        return f"ServiceM8 Credentials for {self.company_uuid}"
    

class Client(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ghl_id = models.CharField(null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    mobile = models.CharField(max_length=25, null=True, blank=True)
    address = models.TextField(null=True, blank=True)



class Job(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ghl_id = models.CharField(null=True, blank=True)
    status = models.CharField(null=True, blank=True)
    client = models.ForeignKey(Client, related_name='job', on_delete=models.SET_NULL,  null=True, blank=True)
    job_address = models.TextField(null=True, blank=True)



class ServiceM8Log(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=100)
    status = models.CharField(max_length=50)
    
    job_uuid = models.CharField(max_length=100, null=True, blank=True)
    client_uuid = models.CharField(max_length=100, null=True, blank=True)
    
    servicem8_data = models.TextField(null=True, blank=True)
    
    job_link_successful = models.BooleanField(default=False)
    client_link_successful = models.BooleanField(default=False)
    ghl_job_id = models.CharField(max_length=100, null=True, blank=True)
    ghl_client_id = models.CharField(max_length=100, null=True, blank=True)
    
    error_message = models.TextField(null=True, blank=True)
    stack_trace = models.TextField(null=True, blank=True)
    
    def set_servicem8_data(self, data_dict):
        self.servicem8_data = json.dumps(data_dict)
    
    def get_servicem8_data(self):
        if self.servicem8_data:
            return json.loads(self.servicem8_data)
        return {}


    
    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['event_type']),
            models.Index(fields=['job_uuid']),
            models.Index(fields=['client_uuid']),
            models.Index(fields=['status']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.timestamp} - {self.event_type} - {self.status}"
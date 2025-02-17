# Create your models here.
from django.db import models
import uuid

class CoughAudio(models.Model):
    file = models.FileField(upload_to='media/raw_audios/')
    upload_time = models.DateTimeField(auto_now_add=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    cough_probability = models.FloatField(null=True, blank=True)  # 咳嗽可能性
    is_cough_detected = models.BooleanField(default=False)  # 是否檢測為咳嗽

    def __str__(self):
        return f"{self.uuid} - {'Cough Detected' if self.is_cough_detected else 'Not Cough'}"
from django.db import models
from django.contrib.auth.models import User


class VideoSource(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255)
    url = models.URLField()
    source_type = models.CharField(
        max_length=10,
        choices=[('rtsp', 'RTSP'), ('mjpg', 'MJPG')],
        default='rtsp'
    )

    def __str__(self):
        return f"{self.name} ({self.user.username if self.user else 'No User'})"


class Recording(models.Model):
    source = models.ForeignKey(VideoSource, on_delete=models.CASCADE)
    file = models.FileField(upload_to='recordings/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Recording of {self.source.name} on {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

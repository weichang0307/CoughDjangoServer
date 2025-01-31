import threading
import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from django.core.management.base import BaseCommand
from ...util import convert_cough_to_music

class FileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            print(f"New file detected: {event.src_path}")
            threading.Thread(target=self.process_file, args=(event.src_path,)).start()

    def process_file(self, file_path):
        try:
            convert_cough_to_music(file_path)
            print(f"Converted {file_path} to music successfully.")
        except Exception as e:
            print(f"Error converting file: {e}")

class Command(BaseCommand):
    help = "Start folder monitor"

    def handle(self, *args, **kwargs):
        path = os.path.join('media', 'cough_audio')
        os.makedirs(path, exist_ok=True)

        event_handler = FileHandler()
        observer = Observer()
        observer.schedule(event_handler, path, recursive=False)
        observer.start()

        self.stdout.write(f"Monitoring folder: {path}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
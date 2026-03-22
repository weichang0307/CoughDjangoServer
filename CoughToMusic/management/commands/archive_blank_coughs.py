from __future__ import annotations

import csv
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from CoughToMusic.services.library import archive_blank_cough_payload


class Command(BaseCommand):
    help = "Archive existing blank cough WAVs from user folders under MEDIA_ROOT."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            action="append",
            dest="users",
            default=[],
            help="Process only the specified user folder. May be supplied multiple times.",
        )

    def handle(self, *args, **options):
        media_root = getattr(settings, "MEDIA_ROOT", None)
        if not media_root:
            raise CommandError("MEDIA_ROOT is not configured.")
        if not os.path.isdir(media_root):
            raise CommandError(f"MEDIA_ROOT does not exist: {media_root}")

        skipped_names = {"public_cough", "public_music", "public_motif", "import_cough", "archive"}
        requested_users = set(options.get("users") or [])
        total_users = 0
        total_archived = 0
        total_file_failures = 0
        failures = []

        for entry_name in sorted(os.listdir(media_root)):
            entry_path = os.path.join(media_root, entry_name)
            if not os.path.isdir(entry_path) or entry_name in skipped_names:
                continue
            if requested_users and entry_name not in requested_users:
                continue

            total_users += 1
            try:
                archived_count, file_failures = self._archive_user_coughs(entry_name)
                total_archived += archived_count
                total_file_failures += file_failures
                self.stdout.write(f"{entry_name}: archived {archived_count}")
            except Exception as exc:
                failures.append((entry_name, str(exc)))
                self.stderr.write(f"{entry_name}: error {exc}")

        summary = (
            f"Completed blank cough cleanup for {total_users} user folders; "
            f"archived {total_archived} blank coughs; file failures {total_file_failures}."
        )
        if failures:
            self.stdout.write(self.style.WARNING(f"{summary} User failures: {len(failures)}."))
            for entry_name, message in failures:
                self.stdout.write(f"FAILED {entry_name}: {message}")
            return

        self.stdout.write(self.style.SUCCESS(summary))

    def _archive_user_coughs(self, user_id):
        cough_table_path = os.path.join(settings.MEDIA_ROOT, user_id, "cough_audio", "cough_table.csv")
        if not os.path.exists(cough_table_path):
            return 0

        with open(cough_table_path, newline="", encoding="utf-8") as handle:
            filenames = sorted(
                {
                    row.get("filename", "").strip()
                    for row in csv.DictReader(handle)
                    if row.get("filename", "").strip().endswith(".wav")
                }
            )

        archived_count = 0
        file_failures = 0
        for filename in filenames:
            self.stdout.write(f"{user_id}/{filename}: scanning")
            try:
                result = archive_blank_cough_payload({"userId": user_id, "filename": filename})
            except Exception as exc:
                file_failures += 1
                self.stderr.write(f"{user_id}/{filename}: error {exc}")
                continue
            if result.get("archived"):
                archived_count += 1
                self.stdout.write(f"{user_id}/{filename}: archived")
            else:
                self.stdout.write(f"{user_id}/{filename}: kept")
        return archived_count, file_failures

import logging
import os
import sys

from paramiko.util import ClosingContextManager

from django.apps import apps as django_apps

logging.basicConfig(format='%(asctime)s %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p')
logger = logging.getLogger(__name__)


class SFTPClientError(Exception):
    pass


class SFTPClient(ClosingContextManager):

    """Wraps open_sftp with folder defaults for copy (and archive).

    Copy is two steps; put then rename.
    """

    def __init__(self, ssh_conn=None, dst_path=None, dst_tmp_path=None,
                 src_path=None, verbose=None):
        app_config = django_apps.get_app_config('edc_sync_files')
        self.src_path = src_path or app_config.source_folder
        self.dst_path = dst_path or app_config.destination_folder
        self.dst_tmp_path = dst_tmp_path or app_config.destination_tmp_folder
        self.ssh_conn = ssh_conn
        self._sftp_client = None
        self.verbose = verbose
        self.progress = 0

    def connect(self):
        self._sftp_client = self.ssh_conn.open_sftp()
        return self

    def close(self):
        self._sftp_client.close()

    def copy(self, filename=None):
        """Puts on destination as a temp file, renames on the destination.
        """
        dst_tmp = os.path.join(self.dst_tmp_path, f'{filename}.tmp')
        dst = os.path.join(self.dst_path, filename)
        src = os.path.join(self.src_path, filename)
        self.put(src=src, dst=dst_tmp,
                 callback=self.update_progress, confirm=True)
        self.rename(src=dst_tmp, dst=dst)

    def put(self, src=None, dst=None, callback=None, confirm=None):
        if not os.path.exists(src):
            raise SFTPClientError(f'Source file does not exist. Got \'{src}\'')
        self.progress = 0
        try:
            self._sftp_client.put(src, dst, callback=callback, confirm=confirm)
        except IOError as e:
            raise SFTPClientError(
                f'IOError. Failed to copy {src}. Got {e}')
        if self.verbose:
            logger.info(f'Copied {src} to {dst}')
            sys.stdout.write('\n')

    def rename(self, src=None, dst=None):
        try:
            self._sftp_client.rename(src, dst)
        except IOError as e:
            raise SFTPClientError(
                f'IOError. Failed to rename {src} to {dst}. Got {e}')

    def update_progress(self, sent_bytes, total_bytes):
        self.progress = (sent_bytes / total_bytes) * 100
        if self.verbose:
            sys.stdout.write(f'Progress {self.progress}% \r')
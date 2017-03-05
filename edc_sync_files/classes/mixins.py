import socket
import time
import paramiko
import getpass


from builtins import ConnectionRefusedError, ConnectionResetError
from django.utils import timezone

from paramiko import AutoAddPolicy
from paramiko.ssh_exception import BadHostKeyException, AuthenticationException, SSHException

from ..constants import REMOTE, LOCALHOST
from .transaction_messages import transaction_messages


class SSHConnectMixin(object):

    def connect(self, host):
        """Connects the ssh instance.
        If :param:`ssh` is not provided will connect `self.ssh`.
        """
        device, username = (
            self.host, self.user) if host == REMOTE else (
                LOCALHOST, getpass.getuser())
        ssh = paramiko.SSHClient()
        if self.trusted_host:
            ssh.set_missing_host_key_policy(AutoAddPolicy())
        while True:
            try:
                ssh.connect(
                    device,
                    username=username,
                    timeout=5,
                    banner_timeout=5,
                    compress=True,
                )
                message = 'Connected to host {}. '.format(device)
                transaction_messages.add_message('success', message, network=True)
                break
            except (socket.timeout, ConnectionRefusedError) as e:
                message = 'ConnectionRefusedError {}. {} for {}@{}...'.format(
                    timezone.now(), str(e), username, device)
                transaction_messages.add_message('error', message, network=True)
                return False
            except AuthenticationException as e:
                message = ' AuthenticationException Got {} for user {}@{}'.format(
                    str(e)[0:-1], username, device)
                transaction_messages.add_message('error', message, permission=True)
                return False
            except BadHostKeyException as e:
                message = (
                    ' BadHostKeyException. Add server to known_hosts on host {}.'
                    ' Got {}.'.format(e, device)
                )
                transaction_messages.add_message('error', message, permission=True)
                return False
            except socket.gaierror:
                message = (
                    'Hostname {} not known or not available'.format(device))
                transaction_messages.add_message('error', message, network=True)
                return False
            except ConnectionResetError as e:
                message = (
                    ' ConnectionResetError {} for {}@{}'.format(str(e), username, device))
                transaction_messages.add_message('error', message, network=True)
                return False
            except SSHException as e:
                message = ' SSHException {} for {}@{}'.format(str(e), self.user, device)
                transaction_messages.add_message('error', message)
                return False
            except OSError as e:
                transaction_messages.add_message('error', str(e), network=True)
                return False
        return ssh

    def reconnect(self, host):
        self.connect(host)
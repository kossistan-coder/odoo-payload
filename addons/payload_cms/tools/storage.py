# -*- coding: utf-8 -*-
"""File storage of the upload collections.

Two backends share the same interface (``put`` / ``get`` / ``delete`` / ``url``):

* ``native`` (default): Odoo attachments (``ir.attachment``, filestore); the
  key of a file is the attachment ID;
* ``s3``: any S3-compatible object storage (AWS S3, MinIO, Scaleway,
  Cloudflare R2...); the key of a file is its object key. The client is a small
  AWS Signature V4 implementation on top of ``requests`` (no boto3 needed).

Settings are stored as JSON in the ``payload_cms.storage`` system parameter.
Environment variables (``PAYLOAD_STORAGE``, ``PAYLOAD_S3_*``) or the matching
odoo.conf options (``payload_storage``, ``payload_s3_*``) override them, so the
storage can be configured from docker compose only.
"""
import datetime
import hashlib
import hmac
import json
import logging
import os
import re
from urllib.parse import quote, urlsplit

import requests

from odoo.tools import config as odoo_config

_logger = logging.getLogger(__name__)

PARAM = 'payload_cms.storage'
BACKENDS = ('native', 's3')
DEFAULTS = {
    'backend': 'native',
    'endpoint': '',
    'region': 'us-east-1',
    'bucket': '',
    'accessKey': '',
    'secretKey': '',
    'prefix': '',
    'addressing': 'path',     # path (MinIO) | virtual (bucket.host)
    'publicUrl': '',
    'delivery': 'proxy',      # proxy (through Odoo) | public (links / redirects to publicUrl)
}
# setting -> environment variable (the odoo.conf option is the lowercase name)
ENV_VARS = {
    'backend': 'PAYLOAD_STORAGE',
    'endpoint': 'PAYLOAD_S3_ENDPOINT',
    'region': 'PAYLOAD_S3_REGION',
    'bucket': 'PAYLOAD_S3_BUCKET',
    'accessKey': 'PAYLOAD_S3_ACCESS_KEY',
    'secretKey': 'PAYLOAD_S3_SECRET_KEY',
    'prefix': 'PAYLOAD_S3_PREFIX',
    'addressing': 'PAYLOAD_S3_ADDRESSING',
    'publicUrl': 'PAYLOAD_S3_PUBLIC_URL',
    'delivery': 'PAYLOAD_S3_DELIVERY',
}
TEST_KEY = '.payload-connection-test'


class StorageError(Exception):
    pass


# ----------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------
def env_overrides():
    """Settings set by environment variables or odoo.conf (environment wins)."""
    result = {}
    for key, var in ENV_VARS.items():
        value = os.environ.get(var)
        if value in (None, ''):
            value = odoo_config.get(var.lower())
        if value not in (None, '', False):
            result[key] = str(value).strip()
    return result


def _normalize(settings):
    if settings.get('backend') not in BACKENDS:
        settings['backend'] = 'native'
    if settings.get('addressing') not in ('path', 'virtual'):
        settings['addressing'] = 'path'
    if settings.get('delivery') not in ('proxy', 'public'):
        settings['delivery'] = 'proxy'
    settings['prefix'] = (settings.get('prefix') or '').strip('/')
    return settings


def stored_settings(env):
    settings = dict(DEFAULTS)
    raw = env['ir.config_parameter'].sudo().get_param(PARAM)
    if raw:
        try:
            settings.update(json.loads(raw))
        except ValueError:
            pass
    return settings


def get_settings(env):
    """Effective settings: stored settings overridden by the environment."""
    return _normalize(dict(stored_settings(env), **env_overrides()))


def set_settings(env, settings):
    stored = {k: settings.get(k, v) for k, v in DEFAULTS.items()}
    env['ir.config_parameter'].sudo().set_param(PARAM, json.dumps(stored))


def public_settings(settings):
    """Settings exposed to the admin (secret key hidden)."""
    return {
        'backend': settings['backend'],
        'delivery': settings['delivery'],
        'envKeys': sorted(env_overrides()),
    }


# ----------------------------------------------------------------------
# Backends
# ----------------------------------------------------------------------
class NativeBackend:
    """Odoo attachments linked to ``owner`` (key = attachment ID)."""
    name = 'native'

    def __init__(self, env, owner=None):
        self.env = env
        self.owner = owner

    def put(self, key, content, mimetype):
        vals = {'name': key.rsplit('/', 1)[-1], 'raw': content, 'mimetype': mimetype, 'public': True}
        if self.owner:
            vals.update(res_model=self.owner._name, res_id=self.owner.id)
        return self.env['ir.attachment'].sudo().create(vals).id

    def _attachment(self, key):
        return self.env['ir.attachment'].sudo().browse(int(key)).exists() if key else self.env['ir.attachment']

    def get(self, key):
        attachment = self._attachment(key)
        if not attachment:
            raise StorageError('Attachment %s not found' % key)
        return attachment.raw

    def delete(self, key):
        self._attachment(key).unlink()

    def url(self, key):
        return None


class S3Backend:
    """S3-compatible object storage (key = object key)."""
    name = 's3'

    def __init__(self, settings):
        self.settings = settings
        self.bucket = settings.get('bucket') or ''
        self.region = settings.get('region') or 'us-east-1'
        self.access_key = settings.get('accessKey') or ''
        self.secret_key = settings.get('secretKey') or ''
        self.prefix = (settings.get('prefix') or '').strip('/')
        self.virtual = settings.get('addressing') == 'virtual'
        self.endpoint = (settings.get('endpoint') or 'https://s3.%s.amazonaws.com' % self.region).rstrip('/')
        self.public_url = (settings.get('publicUrl') or '').rstrip('/')
        self.timeout = 30

    def check_config(self):
        missing = [label for key, label in (('bucket', 'bucket'), ('accessKey', 'access key'), ('secretKey', 'secret key'))
                   if not self.settings.get(key)]
        if missing:
            raise StorageError('S3 storage: missing %s.' % ', '.join(missing))

    def object_key(self, key):
        return '%s/%s' % (self.prefix, key) if self.prefix else key

    # -- signed requests ---------------------------------------------------
    def _url(self, key=''):
        parts = urlsplit(self.endpoint)
        base_path = parts.path.rstrip('/')
        if self.virtual:
            host = '%s.%s' % (self.bucket, parts.netloc)
            path = '%s/%s' % (base_path, key)
        else:
            host = parts.netloc
            path = '%s/%s/%s' % (base_path, self.bucket, key) if key else '%s/%s' % (base_path, self.bucket)
        return parts.scheme or 'https', host, quote(path, safe='/~')

    def _request(self, method, key='', body=b'', headers=None, params=None, stream=False):
        self.check_config()
        scheme, host, path = self._url(key)
        params = params or {}
        now = datetime.datetime.now(datetime.timezone.utc)
        amz_date, date = now.strftime('%Y%m%dT%H%M%SZ'), now.strftime('%Y%m%d')
        payload_hash = hashlib.sha256(body).hexdigest()
        headers = dict({k.lower(): v for k, v in (headers or {}).items()},
                       host=host, **{'x-amz-date': amz_date, 'x-amz-content-sha256': payload_hash})
        query = '&'.join('%s=%s' % (quote(k, safe='-_.~'), quote(str(v), safe='-_.~'))
                         for k, v in sorted(params.items()))
        signed = ';'.join(sorted(headers))
        canonical = '\n'.join([method, path, query,
                               ''.join('%s:%s\n' % (k, str(headers[k]).strip()) for k in sorted(headers)),
                               signed, payload_hash])
        scope = '%s/%s/s3/aws4_request' % (date, self.region)
        to_sign = '\n'.join(['AWS4-HMAC-SHA256', amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
        signing_key = ('AWS4' + self.secret_key).encode()
        for part in (date, self.region, 's3', 'aws4_request'):
            signing_key = hmac.new(signing_key, part.encode(), hashlib.sha256).digest()
        signature = hmac.new(signing_key, to_sign.encode(), hashlib.sha256).hexdigest()
        headers['authorization'] = 'AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s' % (
            self.access_key, scope, signed, signature)
        url = '%s://%s%s%s' % (scheme, host, path, '?' + query if query else '')
        try:
            return requests.request(method, url, data=body or None, headers=headers, timeout=self.timeout, stream=stream)
        except requests.RequestException as e:
            raise StorageError('S3 storage: cannot reach %s (%s)' % (self.endpoint, e)) from e

    @staticmethod
    def _error(response, what):
        code = re.search(r'<Code>(.*?)</Code>', response.text or '')
        message = re.search(r'<Message>(.*?)</Message>', response.text or '')
        detail = ': '.join(m.group(1) for m in (code, message) if m) or 'HTTP %s' % response.status_code
        return StorageError('S3 storage: %s failed (%s)' % (what, detail))

    # -- backend interface -------------------------------------------------
    def put(self, key, content, mimetype):
        key = self.object_key(key)
        response = self._request('PUT', key, body=content, headers={'content-type': mimetype or 'application/octet-stream'})
        if response.status_code >= 300:
            raise self._error(response, 'upload of %s' % key)
        return key

    def get(self, key):
        response = self._request('GET', key)
        if response.status_code >= 300:
            raise self._error(response, 'download of %s' % key)
        return response.content

    def delete(self, key):
        response = self._request('DELETE', key)
        if response.status_code >= 300 and response.status_code != 404:
            raise self._error(response, 'deletion of %s' % key)

    def exists(self, key):
        return self._request('HEAD', key).status_code == 200

    def url(self, key):
        """Public URL of the object (``publicUrl`` + key), or None."""
        return '%s/%s' % (self.public_url, quote(key, safe='/~')) if self.public_url else None

    # -- bucket ------------------------------------------------------------
    def bucket_exists(self):
        response = self._request('HEAD')
        if response.status_code == 404:
            return False
        if response.status_code >= 300:
            raise StorageError('S3 storage: bucket "%s" is not accessible (HTTP %s, check the credentials).'
                               % (self.bucket, response.status_code))
        return True

    def create_bucket(self):
        body = b''
        if self.region != 'us-east-1':
            body = ('<CreateBucketConfiguration xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                    '<LocationConstraint>%s</LocationConstraint></CreateBucketConfiguration>' % self.region).encode()
        response = self._request('PUT', body=body)
        if response.status_code >= 300:
            raise self._error(response, 'creation of the bucket "%s"' % self.bucket)

    def test(self, create_bucket=False):
        """Check the bucket (optionally create it), then write / read / delete an object."""
        created = False
        if not self.bucket_exists():
            if not create_bucket:
                raise StorageError('S3 storage: the bucket "%s" does not exist.' % self.bucket)
            self.create_bucket()
            created = True
        key = self.put(TEST_KEY, b'ok', 'text/plain')
        if self.get(key) != b'ok':
            raise StorageError('S3 storage: the test object cannot be read back.')
        self.delete(key)
        return 'Connection to the bucket "%s" succeeded%s.' % (self.bucket, ' (bucket created)' if created else '')


def get_backend(env, name=None, owner=None, settings=None):
    """Backend ``name`` (default: the selected one) built from the current settings."""
    settings = settings or get_settings(env)
    name = name or settings['backend']
    if name == 's3':
        return S3Backend(settings)
    return NativeBackend(env, owner)

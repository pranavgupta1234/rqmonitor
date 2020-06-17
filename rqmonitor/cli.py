"""
This reference script has been taken from rq-dashboard with some modifications
"""

import importlib
import logging
import os
import sys
from urllib.parse import quote as urlquote, urlunparse
from redis.connection import (URL_QUERY_ARGUMENT_PARSERS,
                              UnixDomainSocketConnection,
                              SSLConnection)
from urllib.parse import urlparse, parse_qs, unquote

import click
from flask import Flask, Response, request

from rqmonitor.defaults import RQ_MONITOR_REDIS_URL, RQ_MONITOR_REFRESH_INTERVAL
from rqmonitor.version import VERSION
from rqmonitor.bp import monitor_blueprint


logger = logging.getLogger("werkzeug")


def add_basic_auth(blueprint, username, password, realm="RQ Monitor"):
    """Add HTTP Basic Auth to a blueprint.

    Note this is only for casual use!

    """

    @blueprint.before_request
    def basic_http_auth(*args, **kwargs):
        auth = request.authorization
        if auth is None or auth.password != password or auth.username != username:
            return Response(
                "Please login",
                401,
                {"WWW-Authenticate": 'Basic realm="{}"'.format(realm)},
            )


def create_app_with_blueprint(config=None, username=None, password=None,
                              url_prefix='', blueprint=monitor_blueprint):
    """Return Flask app with default configuration and registered blueprint."""
    app = Flask(__name__)

    # Override with any settings in config file, if given.
    if config:
        app.config.from_object(importlib.import_module(config))

    # Override from a configuration file in the env variable, if present.
    if "RQ_MONITOR_SETTINGS" in os.environ:
        app.config.from_envvar("RQ_MONITOR_SETTINGS")

    # Optionally add basic auth to blueprint and register with app.
    if username:
        add_basic_auth(blueprint, username, password)

    app.register_blueprint(blueprint, url_prefix=url_prefix)

    return app

def check_url(url, decode_components=False):
    """
    Taken from redis-py for basic check before passing URL to redis-py
    Kept here to show error before launching app

    For example::

        redis://[[username]:[password]]@localhost:6379/0
        rediss://[[username]:[password]]@localhost:6379/0
        unix://[[username]:[password]]@/path/to/socket.sock?db=0

    Three URL schemes are supported:

    - ```redis://``
      <https://www.iana.org/assignments/uri-schemes/prov/redis>`_ creates a
      normal TCP socket connection
    - ```rediss://``
      <https://www.iana.org/assignments/uri-schemes/prov/rediss>`_ creates
      a SSL wrapped TCP socket connection
    - ``unix://`` creates a Unix Domain Socket connection

    There are several ways to specify a database number. The parse function
    will return the first specified option:
        1. A ``db`` querystring option, e.g. redis://localhost?db=0
        2. If using the redis:// scheme, the path argument of the url, e.g.
           redis://localhost/0
        3. The ``db`` argument to this function.

    If none of these options are specified, db=0 is used.

    The ``decode_components`` argument allows this function to work with
    percent-encoded URLs. If this argument is set to ``True`` all ``%xx``
    escapes will be replaced by their single-character equivalents after
    the URL has been parsed. This only applies to the ``hostname``,
    ``path``, ``username`` and ``password`` components.

    Any additional querystring arguments and keyword arguments will be
    passed along to the ConnectionPool class's initializer. The querystring
    arguments ``socket_connect_timeout`` and ``socket_timeout`` if supplied
    are parsed as float values. The arguments ``socket_keepalive`` and
    ``retry_on_timeout`` are parsed to boolean values that accept
    True/False, Yes/No values to indicate state. Invalid types cause a
    ``UserWarning`` to be raised. In the case of conflicting arguments,
    querystring arguments always win.

    """
    url = urlparse(url)
    url_options = {}

    for name, value in (parse_qs(url.query)).items():
        if value and len(value) > 0:
            parser = URL_QUERY_ARGUMENT_PARSERS.get(name)
            if parser:
                try:
                    url_options[name] = parser(value[0])
                except (TypeError, ValueError):
                    logger.warning(UserWarning(
                        "Invalid value for `%s` in connection URL." % name
                    ))
            else:
                url_options[name] = value[0]

    if decode_components:
        username = unquote(url.username) if url.username else None
        password = unquote(url.password) if url.password else None
        path = unquote(url.path) if url.path else None
        hostname = unquote(url.hostname) if url.hostname else None
    else:
        username = url.username or None
        password = url.password or None
        path = url.path
        hostname = url.hostname

    # We only support redis://, rediss:// and unix:// schemes.
    if url.scheme == 'unix':
        url_options.update({
            'username': username,
            'password': password,
            'path': path,
            'connection_class': UnixDomainSocketConnection,
        })

    elif url.scheme in ('redis', 'rediss'):
        url_options.update({
            'host': hostname,
            'port': int(url.port or 6379),
            'username': username,
            'password': password,
        })

        # If there's a path argument, use it as the db argument if a
        # querystring value wasn't specified
        if 'db' not in url_options and path:
            try:
                url_options['db'] = int(path.replace('/', ''))
            except (AttributeError, ValueError):
                pass

        if url.scheme == 'rediss':
            url_options['connection_class'] = SSLConnection
    else:
        valid_schemes = ', '.join(('redis://', 'rediss://', 'unix://'))
        raise ValueError('Redis URL must specify one of the following '
                         'schemes (%s)' % valid_schemes)

    return True


@click.command()
@click.option(
    "-b",
    "--bind",
    default="0.0.0.0",
    help="IP or hostname on which to bind HTTP server",
)
@click.option(
    "-p", "--port", default=8899, type=int, help="Port on which to bind HTTP server"
)
@click.option(
    "--url-prefix", default="", help="URL prefix e.g. for use behind a reverse proxy"
)
@click.option(
    "--username", default=None, help="HTTP Basic Auth username (not used if not set)"
)
@click.option("--password", default=None, help="HTTP Basic Auth password")
@click.option(
    "-c",
    "--config",
    default=None,
    help="Configuration file (Python module on search path)",
)
@click.option(
    "-u",
    "--redis-url",
    default=[RQ_MONITOR_REDIS_URL],
    multiple=True,
    help="Redis URL. Can be specified multiple times. Default: redis://127.0.0.1:6379",
)
@click.option(
    "--refresh-interval",
    "--interval",
    "refresh_interval",
    default=RQ_MONITOR_REFRESH_INTERVAL,
    type=int,
    help="Refresh interval in ms. Default: 2000",
)
@click.option(
    "--extra-path",
    default=".",
    multiple=True,
    help="Append specified directories to sys.path",
)
@click.option("--debug/--normal", default=False, help="Enter DEBUG mode")
@click.option(
    "-v", "--verbose", is_flag=True, default=False, help="Enable verbose logging"
)
def run(
    bind,
    port,
    url_prefix,
    username,
    password,
    config,
    redis_url,
    refresh_interval,
    extra_path,
    debug,
    verbose,
):
    """Run the RQ Monitor Flask server.

    All configuration can be set on the command line or through environment
    variables of the form RQ_MONITOR_*. For example RQ_MONITOR_USERNAME.

    A subset of the configuration (the configuration parameters used by the
    underlying flask blueprint) can also be provided in a Python module
    referenced using --config, or with a .cfg file referenced by the
    RQ_MONITOR_SETTINGS environment variable.

    """
    if extra_path:
        sys.path += list(extra_path)

    click.echo("RQ Monitor version {}".format(VERSION))

    app = create_app_with_blueprint(config, username, password, url_prefix, monitor_blueprint)
    app.config["RQ_MONITOR_REDIS_URL"] = redis_url
    app.config["RQ_MONITOR_REFRESH_INTERVAL"] = refresh_interval

    # Conditionally disable Flask console messages
    # See: https://stackoverflow.com/questions/14888799

    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.ERROR)
        logger.error(" * Running on {}:{}".format(bind, port))

    for url in redis_url:
        check_url(url)

    app.run(host=bind, port=port, debug=debug)


def main():
    run(auto_envvar_prefix="RQ_MONITOR")

if __name__ == '__main__':
    main()

import os
import time
import json
import requests

from flask import Flask, jsonify

import logging
import opentracing
from flask_opentracing import FlaskTracing

from jaeger_client import Config

import redis
import redis_opentracing

app = Flask(__name__)

rdb = redis.Redis(host="redis", port=6379, db=0)


def init_tracer(service):
    logging.getLogger('').handlers = []
    logging.basicConfig(format='%(message)s', level=logging.DEBUG)

    config = Config(
        config={
            'sampler': {
                'type': 'const',
                'param': 1,
            },
            'logging': True,
        },
        service_name=service,
    )

    # this call also sets opentracing.tracer
    return config.initialize_tracer()


# starter code
tracer = init_tracer('test-service')

flask_tracer = FlaskTracing(tracer, True, app)
redis_opentracing.init_tracing(flask_tracer, trace_all_classes=False)


@app.route('/')
def hello_world():
    return 'Hello World!'


@app.route('/alpha')
def alpha():
    time.sleep(5)
    return 'This is the Alpha Endpoint!'


@app.route('/beta')
def beta():
    r = requests.get("https://www.google.com/search?q=python")
    dict = {}
    for key, value in r.headers.items():
        dict[key] = value
    return json.dumps(dict, indent=2)


# needed to rename this view to avoid function name collision with redis import
@app.route('/writeredis')
def writeredis():
    url = "https://www.google.com/search?q=python"
    # start tracing the redis client
    redis_opentracing.trace_client(rdb)

    if rdb.exists(url):
        logging.info("Cache-hit")
        return rdb.get(url)

    logging.info("Cache-miss")
    r = requests.get("https://www.google.com/search?q=python")
    dict = {}
    # put the first 50 results into dict
    values = list(r.headers.items())
    for k, v in values:
        dict[k] = v
    headers = json.dumps(dict, indent=2)
    rdb.set(url, headers)
    return headers


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

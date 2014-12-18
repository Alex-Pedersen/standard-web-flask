import logging

from fabric.api import abort, run, local, cd, env, roles, execute, prefix
from webassets.script import CommandLineEnvironment
import requests

from standardweb import app
from standardweb.assets import assets_env


CODE_DIR = '/home/sbezboro/standard-web-flask'
ENV_DIR = '/home/sbezboro/standard-web-flask-env'
WEB_SERVICE = 'standard-web-flask'
TASK_SERVICE = 'standard-web-celery'
SCHEDULE_SERVICE = 'standard-web-celery-beat'

env.roledefs = {
    'web': ['208.110.64.130']
}


def deploy():
    local("git pull")

    execute(update_and_restart_services)

    rollbar_record_deploy()


@roles('web')
def update_and_restart_services():
    with cd(CODE_DIR):
        with prefix('source %s/bin/activate' % ENV_DIR):
            run("git pull")

            result = run("pip install -r requirements.txt --quiet")
            if result.failed:
                abort('Could not install required packages. Aborting.')

            log = logging.getLogger('webassets')
            log.addHandler(logging.StreamHandler())
            log.setLevel(logging.DEBUG)
            cmdenv = CommandLineEnvironment(assets_env, log)
            cmdenv.build()

            run('supervisorctl restart %s' % WEB_SERVICE)
            run('supervisorctl restart %s' % TASK_SERVICE)
            run('supervisorctl restart %s' % SCHEDULE_SERVICE)


def rollbar_record_deploy():
    access_token = app.config['ROLLBAR_ACCESS_TOKEN']
    environment = 'production'

    username = local('whoami', capture=True)
    revision = local('git log -n 1 --pretty=format:"%H"', capture=True)

    resp = requests.post('https://api.rollbar.com/api/1/deploy/', {
        'access_token': access_token,
        'environment': environment,
        'local_username': username,
        'rollbar_username': username,
        'revision': revision
    }, timeout=3)

    if resp.status_code == 200:
        print "Deploy recorded successfully."
    else:
        print "Error recording deploy:", resp.text

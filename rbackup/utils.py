import os
import sys
import yaml
import glob
import select
import atexit

from rbackup import config
from rbackup.log import LOG
from rbackup.asset import Asset
from rbackup.target import Target


def on_battery():
    for bat_stat_file in glob.glob('/sys/class/power_supply/BAT*/status'):
        with open(bat_stat_file) as f:
            if f.read().rstrip() == 'Discharging':
                return True
    return False


def proc_exists(pid):
    assert isinstance(pid, int)
    try:
        os.kill(pid, 0)
    except Exception as e:
        return False
    return True


def check_process(pid_file):
    if os.path.isfile(pid_file):
        pid = None
        with open(pid_file, 'r') as f:
            pid = int(f.read())
        if proc_exists(pid):
            return True, pid
        else:
            return True, None

    else:
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid())[:-1])
        return False, None


def process_is_alone(pid_file, force=False):
    exit_handler = lambda: os.remove(pid_file)
    atexit.register(exit_handler)
    file_is, pid = check_process(pid_file)
    if file_is and pid:
        LOG.warning('Process already in progress: %s (%s)', pid, pid_file)
        return False
    elif file_is and not pid:
        LOG.warning('Pid file process is dead: %s (%s)', pid, pid_file)
        if force:
            LOG.warning('FORCE mode in effect. Removing: %s', pid_file)
            exit_handler()
        else:
            return False
    return True


def read_config_file(config_files):
    for config_file in config_files:
        try:
            with open(config_file, 'r') as f:
                LOG.debug('Reading config from: %s', config_file)
                return yaml.load(f)
        except IOError as e:
            continue


def read_config(config_files=config.DEFAULT_CONFIG_FILE_ORDER, stdin=False):
    config = {}
    config.update(read_config_file(config_files))
    if stdin:
        config.update(read_config_stdin())
    return config


def parse_config(config):
    # always have local target available
    targets = {
        'local': Target('local', '/', host=None, port=None, ping=False),
    }
    for target in config['targets']:
        targets[target['id']] = Target.from_dict(target)

    assets = {}
    for asset_dict in config['assets']:
        assets[asset_dict['id']] = Asset.from_dict(asset_dict)

    return (assets, targets)


def file_has_input(file):
    r, _, _ = select.select([file], [], [], 0)
    if r:
        return True
    else:
        return False


def read_config_stdin():
    if sys.stdin.isatty():
        LOG.warning('STDIN is a terminal, ignoring!')
        return {}
    if not file_has_input(sys.stdin):
        LOG.warning('No input found in STDIN!')
        return {}

    LOG.warning('Reading config from STDIN...')
    try:
        return yaml.load(sys.stdin)
    except ValueError as e:
        return {}


def print_config(assets, targets):
    print('Assets:')
    for  asset in assets.values():
        if asset.target == 'local':
            target = ''
        else:
            target = '{user}@{host}:{port}:{dest}'.format(
                **vars(targets[asset.target]))
        print(' * {id} - {src} -> {0}{dest} ({type})'.format(
            target, **vars(asset)))

def merge_config_into_opts(conf, opts):
    # TODO maybe limit what options we actually merge?
    for option, value in conf.get('config', {}).items():
        opts['--'+option] = value
    return opts


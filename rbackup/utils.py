import os
import json
import glob
import select
import atexit
import config as conf
from log import LOG

def on_battery():
    for bat_stat_file in glob.glob('/sys/class/power_supply/BAT*/status'):
        with open(bat_stat_file) as f:
            if f.read().rstrip() == 'Discharging':
                return True


def exit_handler():
    os.remove(DEFAULT_PID_FILE)


def proc_exists(pid):
    try:
        os.kill(pid, 0)
    except Exception as e:
        return False
    return True


def check_process(pid_file):
    if os.path.isfile(pid_file):
        pid = None
        with open(pid_file, 'r') as f:
            pid = f.read()
        if proc_exists(pid):
            return True, True
        else:
            return True, False

    else:
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid())[:-1])
        return False, False


def verify_process_is_alone(pid_file):
    atexit.register(exit_handler)
    file_is, process_is = check_process(pid_file)
    if file_is and process_is:
        log.warning(
            'Process already in progress: {} ({})'.format(pid, pid_file))
        sys.exit(0)
    elif file_is and not process_is:
        log.warning('Pid file process is dead: {} ({})'.format(pid, pid_file))
        if args.force:
            log.warning('Removing: {}'.format(pid_file))
            exit_handler()
        else:
            sys.exit(0)


def read_config_file(config_files):
    for config_file in config_files:
        try:
            with open(config_file, 'r') as f:
                LOG.debug('Reading config from: %s', config_file)
                return json.load(f)
        except IOError as e:
            continue
    LOG.error('No config file found!')
    sys.exit(1)


def file_has_input(file):
    r, w, x = select.select([file], [], [], 0)
    if r:
        return True
    else:
        return False


def read_config_stdin():
    if not sys.stdin.isatty() and file_has_input(sys.stdin):
        LOG.warning('Reading config from STDIN...')
        try:
            return json.load(sys.stdin)
        except ValueError as e:
            return {}
    return {}


def read_config(config_files=conf.DEFAULT_CONFIG_FILE_ORDER, stdin=False):
    config = {}
    config.update(read_config_file(config_files))
    if stdin:
        config.update(read_config_stdin())
    return config


def print_config(conf):
    print('Assets:')
    for  asset in conf['assets'].values():
        if asset.get('target', 'local') == 'local':
            target = ''
        else:
            target = '{user}@{host}:{port}:{dest}'.format(
                **conf['targets'][asset['target']])
        print(' * {id} - {src} -> {0}{dest} ({type})'.format(target, **asset))